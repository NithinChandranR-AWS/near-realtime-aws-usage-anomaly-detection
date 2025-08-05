const zlib = require('zlib');
const crypto = require('crypto');
const AWS = require('aws-sdk');
const accountEnrichment = require('./account_enrichment');

// OpenSearch client setup
const endpoint = process.env.OPENSEARCH_DOMAIN_ENDPOINT;
const enableAccountEnrichment = process.env.ENABLE_ACCOUNT_ENRICHMENT === 'true';
const enableOrgContext = process.env.ENABLE_ORG_CONTEXT === 'true';

// AWS clients
const organizations = new AWS.Organizations();
const cloudwatch = new AWS.CloudWatch();

// Account metadata cache (in production, use DynamoDB or ElastiCache)
const accountMetadataCache = new Map();

// Metrics tracking
const metrics = {
    processedEvents: 0,
    failedEvents: 0,
    enrichedAccounts: new Set(),
    errors: [],
    cacheHits: 0,
    cacheMisses: 0,
    organizationsApiCalls: 0
};

function resetMetrics() {
    metrics.processedEvents = 0;
    metrics.failedEvents = 0;
    metrics.enrichedAccounts = new Set();
    metrics.errors = [];
    metrics.cacheHits = 0;
    metrics.cacheMisses = 0;
    metrics.organizationsApiCalls = 0;
}

// Publish custom metrics to CloudWatch
async function publishMetrics() {
    try {
        const params = {
            Namespace: 'AWS/Lambda/MultiAccountAnomalyDetector',
            MetricData: [
                {
                    MetricName: 'ProcessedEvents',
                    Value: metrics.processedEvents,
                    Unit: 'Count'
                },
                {
                    MetricName: 'FailedEvents',
                    Value: metrics.failedEvents,
                    Unit: 'Count'
                },
                {
                    MetricName: 'EnrichedAccounts',
                    Value: metrics.enrichedAccounts.size,
                    Unit: 'Count'
                },
                {
                    MetricName: 'CacheHitRate',
                    Value: metrics.cacheHits / (metrics.cacheHits + metrics.cacheMisses) * 100 || 0,
                    Unit: 'Percent'
                },
                {
                    MetricName: 'OrganizationsApiCalls',
                    Value: metrics.organizationsApiCalls,
                    Unit: 'Count'
                }
            ]
        };
        
        await cloudwatch.putMetricData(params).promise();
    } catch (error) {
        console.warn('Failed to publish metrics:', error.message);
    }
}

exports.handler = async (event, context) => {
    const startTime = Date.now();
    
    try {
        // Reset metrics for this invocation
        resetMetrics();
        
        const payload = Buffer.from(event.awslogs.data, 'base64');
        const parsed = JSON.parse(zlib.gunzipSync(payload).toString('utf8'));
        
        console.log('Processing logs from account:', parsed.owner);
        console.log('Log group:', parsed.logGroup);
        console.log('Log stream:', parsed.logStream);
        console.log('Total log events:', parsed.logEvents.length);
        
        const bulkRequestBody = [];
    
    for (const logEvent of parsed.logEvents) {
        try {
            const cloudTrailRecord = JSON.parse(logEvent.message);
            
            // Skip if not a CloudTrail record
            if (!cloudTrailRecord.Records) {
                continue;
            }
            
            for (const record of cloudTrailRecord.Records) {
                try {
                    // Enhance record with multi-account context using dedicated service
                    if (enableAccountEnrichment) {
                        await accountEnrichment.enrichRecord(record);
                        metrics.enrichedAccounts.add(record.recipientAccountId);
                    }
                    
                    // Create document ID including account ID for uniqueness
                    const id = crypto.createHash('sha256')
                        .update(`${record.recipientAccountId}-${record.eventID}`)
                        .digest('hex');
                    
                    const action = { index: { _id: id } };
                    const document = {
                        ...record,
                        // Add enhanced fields
                        '@timestamp': new Date(record.eventTime).toISOString(),
                        'accountAlias': record.accountAlias || record.recipientAccountId,
                        'organizationId': record.organizationId || 'unknown',
                        'organizationalUnit': record.organizationalUnit || 'unknown',
                        'accountType': record.accountType || 'unknown', // dev/staging/prod
                        'costCenter': record.costCenter || 'unknown',
                        // Add search-friendly fields
                        'eventNameKeyword': record.eventName,
                        'userIdentityType': record.userIdentity?.type || 'unknown',
                        'sourceIPAddress': record.sourceIPAddress || 'unknown'
                    };
                    
                    bulkRequestBody.push(action);
                    bulkRequestBody.push(document);
                    metrics.processedEvents++;
                } catch (recordError) {
                    console.error(`Error processing record ${record.eventID}:`, recordError);
                    metrics.failedEvents++;
                }
            }
        } catch (error) {
            console.error('Error processing log event:', error);
            console.error('Log event:', logEvent.message);
        }
    }
    
        if (bulkRequestBody.length > 0) {
            const response = await postToOpenSearch(bulkRequestBody);
            const processingTime = Date.now() - startTime;
            
            console.log(`Processing Summary:`);
            console.log(`  - Documents indexed: ${bulkRequestBody.length / 2}`);
            console.log(`  - Events processed: ${metrics.processedEvents}`);
            console.log(`  - Events failed: ${metrics.failedEvents}`);
            console.log(`  - Accounts enriched: ${metrics.enrichedAccounts.size}`);
            console.log(`  - Cache hits: ${metrics.cacheHits}`);
            console.log(`  - Cache misses: ${metrics.cacheMisses}`);
            console.log(`  - Organizations API calls: ${metrics.organizationsApiCalls}`);
            console.log(`  - Processing time: ${processingTime}ms`);
            
            // Publish metrics to CloudWatch
            await publishMetrics();
            await accountEnrichment.publishEnrichmentMetrics();
            
            return {
                statusCode: 200,
                documentsIndexed: bulkRequestBody.length / 2,
                eventsProcessed: metrics.processedEvents,
                eventsFailed: metrics.failedEvents,
                accountsEnriched: metrics.enrichedAccounts.size,
                processingTimeMs: processingTime
            };
        }
        
        console.log('No CloudTrail events to process');
        return {
            statusCode: 200,
            message: 'No CloudTrail events to process',
            eventsProcessed: 0
        };
        
    } catch (error) {
        const processingTime = Date.now() - startTime;
        console.error('Fatal error in Lambda handler:', error);
        console.error(`Processing failed after ${processingTime}ms`);
        
        // Return error response instead of throwing to avoid Lambda retries
        return {
            statusCode: 500,
            error: error.message,
            eventsProcessed: metrics.processedEvents,
            eventsFailed: metrics.failedEvents,
            processingTimeMs: processingTime
        };
    }
};

async function enrichWithAccountContext(record) {
    const accountId = record.recipientAccountId;
    
    // Check cache first
    if (accountMetadataCache.has(accountId)) {
        const metadata = accountMetadataCache.get(accountId);
        Object.assign(record, metadata);
        metrics.cacheHits++;
        return;
    }
    
    metrics.cacheMisses++;
    
    try {
        // Fetch account metadata with retry logic
        const metadata = await fetchAccountMetadataWithRetry(accountId);
        accountMetadataCache.set(accountId, metadata);
        Object.assign(record, metadata);
    } catch (error) {
        console.error(`Failed to enrich account ${accountId}:`, error);
        // Use fallback metadata
        const fallbackMetadata = {
            accountAlias: `account-${accountId}`,
            accountType: 'unknown',
            costCenter: 'unknown'
        };
        accountMetadataCache.set(accountId, fallbackMetadata);
        Object.assign(record, fallbackMetadata);
    }
}

async function fetchAccountMetadataWithRetry(accountId, maxRetries = 3) {
    const AWS = require('aws-sdk');
    const organizations = new AWS.Organizations();
    
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
        try {
            // Try to get account details from Organizations API
            metrics.organizationsApiCalls++;
            const accountDetails = await organizations.describeAccount({
                AccountId: accountId
            }).promise();
            
            // Get account tags for additional metadata
            let tags = {};
            try {
                const tagResponse = await organizations.listTagsForResource({
                    ResourceId: accountId
                }).promise();
                
                tags = tagResponse.Tags.reduce((acc, tag) => {
                    acc[tag.Key] = tag.Value;
                    return acc;
                }, {});
            } catch (tagError) {
                console.warn(`Could not fetch tags for account ${accountId}:`, tagError.message);
            }
            
            return {
                accountAlias: tags.Name || accountDetails.Account.Name || `account-${accountId}`,
                accountType: tags.Environment || tags.Type || determineAccountType(accountDetails.Account.Name),
                costCenter: tags.CostCenter || tags.Team || 'unknown',
                organizationalUnit: await getAccountOU(accountId)
            };
            
        } catch (error) {
            console.warn(`Attempt ${attempt} failed for account ${accountId}:`, error.message);
            
            if (attempt === maxRetries) {
                throw error;
            }
            
            // Exponential backoff
            await new Promise(resolve => setTimeout(resolve, Math.pow(2, attempt) * 1000));
        }
    }
}

async function getAccountOU(accountId) {
    const AWS = require('aws-sdk');
    const organizations = new AWS.Organizations();
    
    try {
        const parents = await organizations.listParents({
            ChildId: accountId
        }).promise();
        
        if (parents.Parents && parents.Parents.length > 0) {
            const parentId = parents.Parents[0].Id;
            if (parentId.startsWith('ou-')) {
                const ou = await organizations.describeOrganizationalUnit({
                    OrganizationalUnitId: parentId
                }).promise();
                return ou.OrganizationalUnit.Name;
            }
        }
        return 'Root';
    } catch (error) {
        console.warn(`Could not determine OU for account ${accountId}:`, error.message);
        return 'unknown';
    }
}

function determineAccountType(accountName) {
    if (!accountName) return 'unknown';
    
    const name = accountName.toLowerCase();
    if (name.includes('prod') || name.includes('production')) return 'production';
    if (name.includes('stag') || name.includes('staging')) return 'staging';
    if (name.includes('dev') || name.includes('development')) return 'development';
    if (name.includes('test') || name.includes('testing')) return 'testing';
    if (name.includes('sandbox') || name.includes('sb')) return 'sandbox';
    
    return 'unknown';
}

async function enrichWithOrgContext(record) {
    // In production, use AWS Organizations API
    // For now, add placeholder organization context
    record.organizationId = process.env.ORGANIZATION_ID || 'org-placeholder';
    record.organizationalUnit = await getOrganizationalUnit(record.recipientAccountId);
}

async function getAccountAlias(accountId) {
    // In production, fetch from AWS Organizations or account tags
    const aliasMap = {
        '123456789012': 'production-main',
        '234567890123': 'staging-env',
        '345678901234': 'development-env'
    };
    return aliasMap[accountId] || `account-${accountId}`;
}

async function getAccountType(accountId) {
    // Determine account type based on tags or naming convention
    const alias = await getAccountAlias(accountId);
    if (alias.includes('prod')) return 'production';
    if (alias.includes('stag')) return 'staging';
    if (alias.includes('dev')) return 'development';
    return 'unknown';
}

async function getCostCenter(accountId) {
    // In production, fetch from account tags
    return 'engineering'; // placeholder
}

async function getOrganizationalUnit(accountId) {
    // In production, use Organizations API
    return 'ou-root-workloads'; // placeholder
}

async function postToOpenSearch(body, maxRetries = 3) {
    const https = require('https');
    const aws4 = require('aws4');
    
    const requestBody = body.map(JSON.stringify).join('\n') + '\n';
    
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
        try {
            const options = {
                host: endpoint,
                path: '/cwl-multiaccounts/_bulk',
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-ndjson',
                    'Content-Length': Buffer.byteLength(requestBody)
                },
                body: requestBody,
                timeout: 30000 // 30 second timeout
            };
            
            // Sign the request with AWS credentials
            aws4.sign(options, {
                service: 'es',
                region: process.env.AWS_REGION || 'us-east-1'
            });
            
            const result = await new Promise((resolve, reject) => {
                const req = https.request(options, (res) => {
                    let responseBody = '';
                    res.on('data', (chunk) => responseBody += chunk);
                    res.on('end', () => {
                        if (res.statusCode >= 200 && res.statusCode < 300) {
                            try {
                                const parsed = JSON.parse(responseBody);
                                // Check for partial failures in bulk response
                                if (parsed.errors) {
                                    console.warn('Some documents failed to index:', parsed.items?.filter(item => item.index?.error));
                                }
                                resolve(parsed);
                            } catch (e) {
                                console.warn('Could not parse OpenSearch response, assuming success');
                                resolve({ acknowledged: true, errors: false });
                            }
                        } else {
                            reject(new Error(`OpenSearch returned status ${res.statusCode}: ${responseBody}`));
                        }
                    });
                });
                
                req.on('error', reject);
                req.on('timeout', () => {
                    req.destroy();
                    reject(new Error('Request timeout'));
                });
                
                req.write(requestBody);
                req.end();
            });
            
            return result;
            
        } catch (error) {
            console.warn(`OpenSearch request attempt ${attempt} failed:`, error.message);
            
            if (attempt === maxRetries) {
                console.error(`All ${maxRetries} attempts failed. Last error:`, error);
                throw error;
            }
            
            // Exponential backoff with jitter
            const delay = Math.min(1000 * Math.pow(2, attempt) + Math.random() * 1000, 10000);
            console.log(`Retrying in ${delay}ms...`);
            await new Promise(resolve => setTimeout(resolve, delay));
        }
    }
}
