const zlib = require('zlib');
const crypto = require('crypto');

// OpenSearch client setup
const endpoint = process.env.OPENSEARCH_DOMAIN_ENDPOINT;
const enableAccountEnrichment = process.env.ENABLE_ACCOUNT_ENRICHMENT === 'true';
const enableOrgContext = process.env.ENABLE_ORG_CONTEXT === 'true';

// Account metadata cache (in production, use DynamoDB or ElastiCache)
const accountMetadataCache = new Map();

exports.handler = async (event, context) => {
    const payload = Buffer.from(event.awslogs.data, 'base64');
    const parsed = JSON.parse(zlib.gunzipSync(payload).toString('utf8'));
    
    console.log('Processing logs from account:', parsed.owner);
    console.log('Log group:', parsed.logGroup);
    console.log('Log stream:', parsed.logStream);
    
    const bulkRequestBody = [];
    
    for (const logEvent of parsed.logEvents) {
        try {
            const cloudTrailRecord = JSON.parse(logEvent.message);
            
            // Skip if not a CloudTrail record
            if (!cloudTrailRecord.Records) {
                continue;
            }
            
            for (const record of cloudTrailRecord.Records) {
                // Enhance record with multi-account context
                if (enableAccountEnrichment) {
                    await enrichWithAccountContext(record);
                }
                
                // Add organization context
                if (enableOrgContext) {
                    await enrichWithOrgContext(record);
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
            }
        } catch (error) {
            console.error('Error processing log event:', error);
            console.error('Log event:', logEvent.message);
        }
    }
    
    if (bulkRequestBody.length > 0) {
        const response = await postToOpenSearch(bulkRequestBody);
        console.log(`Successfully indexed ${bulkRequestBody.length / 2} documents`);
        return response;
    }
    
    return 'No CloudTrail events to process';
};

async function enrichWithAccountContext(record) {
    const accountId = record.recipientAccountId;
    
    // Check cache first
    if (accountMetadataCache.has(accountId)) {
        const metadata = accountMetadataCache.get(accountId);
        Object.assign(record, metadata);
        return;
    }
    
    // In production, fetch from AWS Organizations API or a metadata store
    // For now, we'll add placeholder enrichment
    const metadata = {
        accountAlias: await getAccountAlias(accountId),
        accountType: await getAccountType(accountId),
        costCenter: await getCostCenter(accountId)
    };
    
    accountMetadataCache.set(accountId, metadata);
    Object.assign(record, metadata);
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

async function postToOpenSearch(body) {
    const https = require('https');
    const aws4 = require('aws4');
    
    const requestBody = body.map(JSON.stringify).join('\n') + '\n';
    
    const options = {
        host: endpoint,
        path: '/cwl-multiaccounts/_bulk',
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-ndjson',
            'Content-Length': Buffer.byteLength(requestBody)
        },
        body: requestBody
    };
    
    // Sign the request with AWS credentials
    aws4.sign(options, {
        service: 'es',
        region: process.env.AWS_REGION || 'us-east-1'
    });
    
    return new Promise((resolve, reject) => {
        const req = https.request(options, (res) => {
            let responseBody = '';
            res.on('data', (chunk) => responseBody += chunk);
            res.on('end', () => {
                if (res.statusCode >= 200 && res.statusCode < 300) {
                    try {
                        resolve(JSON.parse(responseBody));
                    } catch (e) {
                        resolve({ acknowledged: true });
                    }
                } else {
                    reject(new Error(`OpenSearch returned status ${res.statusCode}: ${responseBody}`));
                }
            });
        });
        
        req.on('error', reject);
        req.write(requestBody);
        req.end();
    });
}
