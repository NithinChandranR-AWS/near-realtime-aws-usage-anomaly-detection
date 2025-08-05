/**
 * Account Enrichment Service
 * 
 * Provides account metadata enrichment with caching, fallback mechanisms,
 * and organizational context for multi-account CloudTrail processing.
 */

const AWS = require('aws-sdk');

// AWS clients
const organizations = new AWS.Organizations();
const dynamodb = new AWS.DynamoDB.DocumentClient();
const cloudwatch = new AWS.CloudWatch();

// Configuration
const CACHE_TABLE_NAME = process.env.ACCOUNT_CACHE_TABLE || 'account-metadata-cache';
const CACHE_TTL_HOURS = parseInt(process.env.CACHE_TTL_HOURS || '24');
const MAX_RETRIES = 3;
const RETRY_DELAY_BASE = 1000; // 1 second

// In-memory cache for Lambda execution context
const memoryCache = new Map();

// Metrics
const enrichmentMetrics = {
    cacheHits: 0,
    cacheMisses: 0,
    dynamodbHits: 0,
    dynamodbMisses: 0,
    organizationsApiCalls: 0,
    enrichmentErrors: 0,
    fallbacksUsed: 0
};

/**
 * Main enrichment function - enriches a CloudTrail record with account metadata
 */
async function enrichRecord(record) {
    const accountId = record.recipientAccountId;
    
    if (!accountId) {
        console.warn('No recipientAccountId found in record');
        return record;
    }
    
    try {
        const metadata = await getAccountMetadata(accountId);
        
        // Enrich the record with metadata
        Object.assign(record, {
            accountAlias: metadata.accountAlias,
            accountType: metadata.accountType,
            organizationalUnit: metadata.organizationalUnit,
            costCenter: metadata.costCenter,
            environment: metadata.environment,
            team: metadata.team,
            businessUnit: metadata.businessUnit,
            complianceLevel: metadata.complianceLevel
        });
        
        return record;
        
    } catch (error) {
        console.error(`Failed to enrich account ${accountId}:`, error);
        enrichmentMetrics.enrichmentErrors++;
        
        // Apply fallback metadata
        const fallbackMetadata = generateFallbackMetadata(accountId);
        Object.assign(record, fallbackMetadata);
        enrichmentMetrics.fallbacksUsed++;
        
        return record;
    }
}

/**
 * Get account metadata with multi-level caching
 */
async function getAccountMetadata(accountId) {
    // Level 1: In-memory cache (fastest)
    if (memoryCache.has(accountId)) {
        const cached = memoryCache.get(accountId);
        if (!isCacheExpired(cached.timestamp)) {
            enrichmentMetrics.cacheHits++;
            return cached.metadata;
        } else {
            memoryCache.delete(accountId);
        }
    }
    
    // Level 2: DynamoDB cache (persistent across Lambda invocations)
    try {
        const dynamoResult = await getDynamoDBCache(accountId);
        if (dynamoResult && !isCacheExpired(dynamoResult.timestamp)) {
            // Update in-memory cache
            memoryCache.set(accountId, dynamoResult);
            enrichmentMetrics.dynamodbHits++;
            return dynamoResult.metadata;
        }
        enrichmentMetrics.dynamodbMisses++;
    } catch (error) {
        console.warn(`DynamoDB cache lookup failed for ${accountId}:`, error.message);
    }
    
    // Level 3: Fetch from AWS Organizations API
    enrichmentMetrics.cacheMisses++;
    const metadata = await fetchAccountMetadataFromAPI(accountId);
    
    // Cache the result
    const cacheEntry = {
        accountId,
        metadata,
        timestamp: Date.now()
    };
    
    // Update both caches
    memoryCache.set(accountId, cacheEntry);
    await updateDynamoDBCache(cacheEntry);
    
    return metadata;
}

/**
 * Fetch account metadata from DynamoDB cache
 */
async function getDynamoDBCache(accountId) {
    const params = {
        TableName: CACHE_TABLE_NAME,
        Key: { accountId }
    };
    
    const result = await dynamodb.get(params).promise();
    return result.Item || null;
}

/**
 * Update DynamoDB cache with account metadata
 */
async function updateDynamoDBCache(cacheEntry) {
    try {
        const params = {
            TableName: CACHE_TABLE_NAME,
            Item: {
                ...cacheEntry,
                ttl: Math.floor(Date.now() / 1000) + (CACHE_TTL_HOURS * 3600)
            }
        };
        
        await dynamodb.put(params).promise();
    } catch (error) {
        console.warn(`Failed to update DynamoDB cache for ${cacheEntry.accountId}:`, error.message);
    }
}

/**
 * Fetch account metadata from AWS Organizations API with retry logic
 */
async function fetchAccountMetadataFromAPI(accountId) {
    for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
        try {
            enrichmentMetrics.organizationsApiCalls++;
            
            // Get basic account information
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
            
            // Get organizational unit information
            const organizationalUnit = await getAccountOrganizationalUnit(accountId);
            
            // Build comprehensive metadata
            const metadata = {
                accountAlias: tags.Name || tags.Alias || accountDetails.Account.Name || `account-${accountId}`,
                accountType: tags.Environment || tags.Type || determineAccountType(accountDetails.Account.Name),
                organizationalUnit: organizationalUnit,
                costCenter: tags.CostCenter || tags.Team || 'unknown',
                environment: tags.Environment || determineEnvironment(accountDetails.Account.Name),
                team: tags.Team || tags.Owner || 'unknown',
                businessUnit: tags.BusinessUnit || tags.BU || 'unknown',
                complianceLevel: tags.ComplianceLevel || tags.DataClassification || 'standard',
                accountStatus: accountDetails.Account.Status,
                joinedTimestamp: accountDetails.Account.JoinedTimestamp,
                lastUpdated: new Date().toISOString()
            };
            
            return metadata;
            
        } catch (error) {
            console.warn(`Attempt ${attempt} failed for account ${accountId}:`, error.message);
            
            if (attempt === MAX_RETRIES) {
                throw error;
            }
            
            // Exponential backoff with jitter
            const delay = RETRY_DELAY_BASE * Math.pow(2, attempt - 1) + Math.random() * 1000;
            await new Promise(resolve => setTimeout(resolve, delay));
        }
    }
}

/**
 * Get the organizational unit for an account
 */
async function getAccountOrganizationalUnit(accountId) {
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
            } else if (parentId.startsWith('r-')) {
                return 'Root';
            }
        }
        
        return 'unknown';
    } catch (error) {
        console.warn(`Could not determine OU for account ${accountId}:`, error.message);
        return 'unknown';
    }
}

/**
 * Determine account type from account name
 */
function determineAccountType(accountName) {
    if (!accountName) return 'unknown';
    
    const name = accountName.toLowerCase();
    
    // Production patterns
    if (name.includes('prod') || name.includes('production') || name.includes('prd')) {
        return 'production';
    }
    
    // Staging patterns
    if (name.includes('stag') || name.includes('staging') || name.includes('stage')) {
        return 'staging';
    }
    
    // Development patterns
    if (name.includes('dev') || name.includes('development') || name.includes('develop')) {
        return 'development';
    }
    
    // Testing patterns
    if (name.includes('test') || name.includes('testing') || name.includes('qa')) {
        return 'testing';
    }
    
    // Sandbox patterns
    if (name.includes('sandbox') || name.includes('sb') || name.includes('demo')) {
        return 'sandbox';
    }
    
    return 'unknown';
}

/**
 * Determine environment from account name
 */
function determineEnvironment(accountName) {
    const accountType = determineAccountType(accountName);
    
    // Map account types to environments
    const environmentMap = {
        'production': 'prod',
        'staging': 'stage',
        'development': 'dev',
        'testing': 'test',
        'sandbox': 'sandbox'
    };
    
    return environmentMap[accountType] || 'unknown';
}

/**
 * Generate fallback metadata when API calls fail
 */
function generateFallbackMetadata(accountId) {
    return {
        accountAlias: `account-${accountId}`,
        accountType: 'unknown',
        organizationalUnit: 'unknown',
        costCenter: 'unknown',
        environment: 'unknown',
        team: 'unknown',
        businessUnit: 'unknown',
        complianceLevel: 'standard',
        accountStatus: 'ACTIVE',
        lastUpdated: new Date().toISOString(),
        fallback: true
    };
}

/**
 * Check if cache entry is expired
 */
function isCacheExpired(timestamp) {
    const now = Date.now();
    const cacheAge = now - timestamp;
    const maxAge = CACHE_TTL_HOURS * 60 * 60 * 1000; // Convert hours to milliseconds
    
    return cacheAge > maxAge;
}

/**
 * Refresh account metadata cache for a specific account
 */
async function refreshAccountCache(accountId) {
    try {
        // Remove from caches
        memoryCache.delete(accountId);
        
        await dynamodb.delete({
            TableName: CACHE_TABLE_NAME,
            Key: { accountId }
        }).promise();
        
        // Fetch fresh data
        const metadata = await getAccountMetadata(accountId);
        
        console.log(`Refreshed cache for account ${accountId}`);
        return metadata;
        
    } catch (error) {
        console.error(`Failed to refresh cache for account ${accountId}:`, error);
        throw error;
    }
}

/**
 * Bulk refresh cache for multiple accounts
 */
async function bulkRefreshCache(accountIds) {
    const results = [];
    
    for (const accountId of accountIds) {
        try {
            const metadata = await refreshAccountCache(accountId);
            results.push({ accountId, status: 'success', metadata });
        } catch (error) {
            results.push({ accountId, status: 'error', error: error.message });
        }
    }
    
    return results;
}

/**
 * Get enrichment metrics
 */
function getEnrichmentMetrics() {
    return {
        ...enrichmentMetrics,
        memoryCacheSize: memoryCache.size,
        cacheHitRate: enrichmentMetrics.cacheHits / (enrichmentMetrics.cacheHits + enrichmentMetrics.cacheMisses) * 100 || 0
    };
}

/**
 * Reset enrichment metrics
 */
function resetEnrichmentMetrics() {
    Object.keys(enrichmentMetrics).forEach(key => {
        if (typeof enrichmentMetrics[key] === 'number') {
            enrichmentMetrics[key] = 0;
        }
    });
}

/**
 * Publish enrichment metrics to CloudWatch
 */
async function publishEnrichmentMetrics() {
    try {
        const metrics = getEnrichmentMetrics();
        
        const params = {
            Namespace: 'AWS/Lambda/AccountEnrichment',
            MetricData: [
                {
                    MetricName: 'CacheHits',
                    Value: metrics.cacheHits,
                    Unit: 'Count'
                },
                {
                    MetricName: 'CacheMisses',
                    Value: metrics.cacheMisses,
                    Unit: 'Count'
                },
                {
                    MetricName: 'DynamoDBHits',
                    Value: metrics.dynamodbHits,
                    Unit: 'Count'
                },
                {
                    MetricName: 'OrganizationsApiCalls',
                    Value: metrics.organizationsApiCalls,
                    Unit: 'Count'
                },
                {
                    MetricName: 'EnrichmentErrors',
                    Value: metrics.enrichmentErrors,
                    Unit: 'Count'
                },
                {
                    MetricName: 'CacheHitRate',
                    Value: metrics.cacheHitRate,
                    Unit: 'Percent'
                }
            ]
        };
        
        await cloudwatch.putMetricData(params).promise();
        console.log('Published enrichment metrics to CloudWatch');
        
    } catch (error) {
        console.warn('Failed to publish enrichment metrics:', error.message);
    }
}

module.exports = {
    enrichRecord,
    getAccountMetadata,
    refreshAccountCache,
    bulkRefreshCache,
    getEnrichmentMetrics,
    resetEnrichmentMetrics,
    publishEnrichmentMetrics
};