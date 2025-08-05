import aws_cdk as core
import aws_cdk.assertions as assertions

from infra.usage_anomaly_detector import UsageAnomalyDetectorStack

# example tests. To run these tests, uncomment this file along with the example
# resource in infra/usage_anomaly_detector.py
def test_sqs_queue_created():
    app = core.App()
    # Set required context values
    app.node.set_context("enable-lambda-trail", "false")
    app.node.set_context("opensearch-version", "OPENSEARCH_2_9")
    
    stack = UsageAnomalyDetectorStack(app, "infra")
    template = assertions.Template.from_stack(stack)
    
    # Test that OpenSearch domain is created
    template.has_resource_properties("AWS::OpenSearchService::Domain", {
        "EngineVersion": "OpenSearch_2.9"
    })
    
    # Test that CloudTrail is created
    template.has_resource_properties("AWS::CloudTrail::Trail", {
        "IsMultiRegionTrail": True,
        "EnableLogFileValidation": True
    })

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
