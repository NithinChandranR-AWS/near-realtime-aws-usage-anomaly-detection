/**
 * Test suite for CrossAccountAnomalyProcessor Lambda function
 */

const { handler } = require('./index');
const zlib = require('zlib');

// Mock AWS SDK
const mockOrganizations = {
    describeAccount: jest.fn(),
    listTagsForResource: jest.fn(),
    listParents: jest.fn(),
    describeOrganizationalUnit: jest.fn()
};

const mockCloudWatch = {
    putMetricData: jest.fn()
};

jest.mock('aws-sdk', () => ({
    Organizations: jest.fn(() => mockOrganizations),
    CloudWatch: jest.fn(() => mockCloudWatch)
}));

// Mock environment variables
process.env.OPENSEARCH_DOMAIN_ENDPOINT = 'test-domain.us-east-1.es.amazonaws.com';
process.env.ENABLE_ACCOUNT_ENRICHMENT = 'true';
process.env.ENABLE_ORG_CONTEXT = 'true';
process.env.AWS_REGION = 'us-east-1';

describe('CrossAccountAnomalyProcessor', () => {
    beforeEach(() => {
        jest.clearAllMocks();
    });

    test('should process CloudTrail logs with account enrichment', async () => {
        // Mock Organizations API responses
        mockOrganizations.describeAccount.mockResolvedValue({
            Account: {
                Id: '123456789012',
                Name: 'production-account'
            }
        });

        mockOrganizations.listTagsForResource.mockResolvedValue({
            Tags: [
                { Key: 'Environment', Value: 'production' },
                { Key: 'CostCenter', Value: 'engineering' }
            ]
        });

        mockOrganizations.listParents.mockResolvedValue({
            Parents: [{ Id: 'ou-root-123456789' }]
        });

        mockOrganizations.describeOrganizationalUnit.mockResolvedValue({
            OrganizationalUnit: { Name: 'Production' }
        });

        // Create test CloudTrail log event
        const cloudTrailRecord = {
            Records: [{
                eventVersion: '1.05',
                userIdentity: {
                    type: 'IAMUser',
                    principalId: 'AIDACKCEVSQ6C2EXAMPLE',
                    arn: 'arn:aws:iam::123456789012:user/testuser'
                },
                eventTime: '2023-01-01T12:00:00Z',
                eventSource: 'ec2.amazonaws.com',
                eventName: 'RunInstances',
                awsRegion: 'us-east-1',
                sourceIPAddress: '192.168.1.1',
                recipientAccountId: '123456789012',
                eventID: 'test-event-id-123'
            }]
        };

        const logEvent = {
            id: '1',
            timestamp: 1672574400000,
            message: JSON.stringify(cloudTrailRecord)
        };

        const logData = {
            messageType: 'DATA_MESSAGE',
            owner: '123456789012',
            logGroup: '/aws/cloudtrail/organization',
            logStream: 'test-stream',
            subscriptionFilters: ['test-filter'],
            logEvents: [logEvent]
        };

        // Compress the log data as CloudWatch Logs does
        const compressed = zlib.gzipSync(JSON.stringify(logData));
        const event = {
            awslogs: {
                data: compressed.toString('base64')
            }
        };

        // Mock the OpenSearch request
        const mockHttpsRequest = jest.fn((options, callback) => {
            const mockResponse = {
                statusCode: 200,
                on: jest.fn((event, handler) => {
                    if (event === 'data') {
                        handler('{"acknowledged": true, "errors": false}');
                    } else if (event === 'end') {
                        handler();
                    }
                })
            };
            callback(mockResponse);
            return {
                on: jest.fn(),
                write: jest.fn(),
                end: jest.fn()
            };
        });

        jest.doMock('https', () => ({
            request: mockHttpsRequest
        }));

        // Execute the handler
        const result = await handler(event, {});

        // Verify results
        expect(result.statusCode).toBe(200);
        expect(result.eventsProcessed).toBe(1);
        expect(result.accountsEnriched).toBe(1);
        expect(mockOrganizations.describeAccount).toHaveBeenCalledWith({
            AccountId: '123456789012'
        });
    });

    test('should handle errors gracefully', async () => {
        // Mock Organizations API to throw error
        mockOrganizations.describeAccount.mockRejectedValue(new Error('API Error'));

        const cloudTrailRecord = {
            Records: [{
                eventTime: '2023-01-01T12:00:00Z',
                eventSource: 'ec2.amazonaws.com',
                eventName: 'RunInstances',
                recipientAccountId: '123456789012',
                eventID: 'test-event-id-456'
            }]
        };

        const logEvent = {
            id: '1',
            timestamp: 1672574400000,
            message: JSON.stringify(cloudTrailRecord)
        };

        const logData = {
            messageType: 'DATA_MESSAGE',
            owner: '123456789012',
            logGroup: '/aws/cloudtrail/organization',
            logStream: 'test-stream',
            subscriptionFilters: ['test-filter'],
            logEvents: [logEvent]
        };

        const compressed = zlib.gzipSync(JSON.stringify(logData));
        const event = {
            awslogs: {
                data: compressed.toString('base64')
            }
        };

        // Execute the handler
        const result = await handler(event, {});

        // Should still process the event with fallback metadata
        expect(result.statusCode).toBe(200);
        expect(result.eventsProcessed).toBe(1);
    });

    test('should cache account metadata', async () => {
        // First call
        mockOrganizations.describeAccount.mockResolvedValue({
            Account: {
                Id: '123456789012',
                Name: 'test-account'
            }
        });

        mockOrganizations.listTagsForResource.mockResolvedValue({
            Tags: []
        });

        const cloudTrailRecord = {
            Records: [{
                eventTime: '2023-01-01T12:00:00Z',
                eventSource: 'ec2.amazonaws.com',
                eventName: 'RunInstances',
                recipientAccountId: '123456789012',
                eventID: 'test-event-id-789'
            }]
        };

        const logEvent = {
            id: '1',
            timestamp: 1672574400000,
            message: JSON.stringify(cloudTrailRecord)
        };

        const logData = {
            messageType: 'DATA_MESSAGE',
            owner: '123456789012',
            logGroup: '/aws/cloudtrail/organization',
            logStream: 'test-stream',
            subscriptionFilters: ['test-filter'],
            logEvents: [logEvent, logEvent] // Same event twice
        };

        const compressed = zlib.gzipSync(JSON.stringify(logData));
        const event = {
            awslogs: {
                data: compressed.toString('base64')
            }
        };

        await handler(event, {});

        // Organizations API should only be called once due to caching
        expect(mockOrganizations.describeAccount).toHaveBeenCalledTimes(1);
    });
});