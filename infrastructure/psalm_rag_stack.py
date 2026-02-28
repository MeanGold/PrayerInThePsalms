"""
AWS CDK Stack for Psalm Recommendation RAG System

This stack defines all AWS resources needed for the Psalm Recommendation RAG system:
- Lambda functions for recommendation handler and data ingestion
- API Gateway REST API
- Amazon Bedrock Knowledge Base with OpenSearch Serverless vector store
- IAM roles and permissions
- CloudWatch log groups and alarms

**Validates: Requirements 6.1, 6.2, 7.1, 7.4**
"""

from aws_cdk import (
    Stack,
    Duration,
    CfnOutput,
    RemovalPolicy,
    aws_lambda as lambda_,
    aws_apigateway as apigateway,
    aws_iam as iam,
    aws_logs as logs,
    aws_cloudwatch as cloudwatch,
    aws_opensearchserverless as opensearchserverless,
    aws_bedrock as bedrock,
)
from constructs import Construct
import json


class PsalmRagStack(Stack):
    """CDK Stack for Psalm Recommendation RAG System."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ===== OpenSearch Serverless Collection for Vector Store =====
        # Requirement 6.1: Vector Store persistence
        
        # Encryption policy for the collection
        encryption_policy = opensearchserverless.CfnSecurityPolicy(
            self,
            "PsalmVectorStoreEncryptionPolicy",
            name="psalm-vector-encryption",
            type="encryption",
            policy=json.dumps({
                "Rules": [
                    {
                        "ResourceType": "collection",
                        "Resource": ["collection/psalm-vector-store"]
                    }
                ],
                "AWSOwnedKey": True
            })
        )

        # Network policy for the collection
        network_policy = opensearchserverless.CfnSecurityPolicy(
            self,
            "PsalmVectorStoreNetworkPolicy",
            name="psalm-vector-network",
            type="network",
            policy=json.dumps([
                {
                    "Rules": [
                        {
                            "ResourceType": "collection",
                            "Resource": ["collection/psalm-vector-store"]
                        },
                        {
                            "ResourceType": "dashboard",
                            "Resource": ["collection/psalm-vector-store"]
                        }
                    ],
                    "AllowFromPublic": True
                }
            ])
        )

        # OpenSearch Serverless Collection
        vector_collection = opensearchserverless.CfnCollection(
            self,
            "PsalmVectorStoreCollection",
            name="psalm-vector-store",
            type="VECTORSEARCH",
            description="Vector store for psalm embeddings and metadata"
        )
        vector_collection.add_dependency(encryption_policy)
        vector_collection.add_dependency(network_policy)

        # ===== IAM Roles =====
        
        # Lambda execution role for recommendation handler
        recommendation_role = iam.Role(
            self,
            "RecommendationHandlerRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Execution role for Psalm Recommendation Handler Lambda",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ]
        )

        # Lambda execution role for data ingestion
        ingestion_role = iam.Role(
            self,
            "DataIngestionHandlerRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Execution role for Data Ingestion Handler Lambda",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ]
        )

        # Bedrock Knowledge Base execution role
        kb_role = iam.Role(
            self,
            "BedrockKnowledgeBaseRole",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
            description="Execution role for Bedrock Knowledge Base"
        )

        # ===== IAM Permissions =====
        
        # Bedrock model invocation permissions (Requirement 7.1)
        bedrock_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream"
            ],
            resources=[
                f"arn:aws:bedrock:{self.region}::foundation-model/amazon.titan-embed-text-v1",
                f"arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0",
                f"arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude-v2"
            ]
        )
        
        recommendation_role.add_to_policy(bedrock_policy)
        ingestion_role.add_to_policy(bedrock_policy)

        # CloudWatch Metrics permissions (Requirement 10.2)
        metrics_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["cloudwatch:PutMetricData"],
            resources=["*"],
            conditions={
                "StringEquals": {
                    "cloudwatch:namespace": "PsalmRecommendationRAG"
                }
            }
        )
        
        recommendation_role.add_to_policy(metrics_policy)
        ingestion_role.add_to_policy(metrics_policy)

        # OpenSearch Serverless permissions for Lambda functions
        aoss_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "aoss:APIAccessAll"
            ],
            resources=[vector_collection.attr_arn]
        )
        
        recommendation_role.add_to_policy(aoss_policy)
        ingestion_role.add_to_policy(aoss_policy)

        # OpenSearch Serverless permissions for Knowledge Base
        kb_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "aoss:APIAccessAll"
                ],
                resources=[vector_collection.attr_arn]
            )
        )

        # Bedrock model access for Knowledge Base
        kb_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:InvokeModel"
                ],
                resources=[
                    f"arn:aws:bedrock:{self.region}::foundation-model/amazon.titan-embed-text-v1"
                ]
            )
        )

        # Data access policy for OpenSearch Serverless
        data_access_policy = opensearchserverless.CfnAccessPolicy(
            self,
            "PsalmVectorStoreDataAccessPolicy",
            name="psalm-vector-data-access",
            type="data",
            policy=json.dumps([
                {
                    "Rules": [
                        {
                            "ResourceType": "collection",
                            "Resource": ["collection/psalm-vector-store"],
                            "Permission": [
                                "aoss:CreateCollectionItems",
                                "aoss:UpdateCollectionItems",
                                "aoss:DescribeCollectionItems"
                            ]
                        },
                        {
                            "ResourceType": "index",
                            "Resource": ["index/psalm-vector-store/*"],
                            "Permission": [
                                "aoss:CreateIndex",
                                "aoss:DescribeIndex",
                                "aoss:ReadDocument",
                                "aoss:WriteDocument",
                                "aoss:UpdateIndex",
                                "aoss:DeleteIndex"
                            ]
                        }
                    ],
                    "Principal": [
                        recommendation_role.role_arn,
                        ingestion_role.role_arn,
                        kb_role.role_arn
                    ]
                }
            ])
        )
        data_access_policy.add_dependency(vector_collection)

        # ===== Bedrock Knowledge Base =====
        # Requirement 6.1, 6.2: Knowledge Base with vector store
        
        knowledge_base = bedrock.CfnKnowledgeBase(
            self,
            "PsalmKnowledgeBase",
            name="psalm-recommendation-kb",
            description="Knowledge Base for psalm embeddings and metadata",
            role_arn=kb_role.role_arn,
            knowledge_base_configuration=bedrock.CfnKnowledgeBase.KnowledgeBaseConfigurationProperty(
                type="VECTOR",
                vector_knowledge_base_configuration=bedrock.CfnKnowledgeBase.VectorKnowledgeBaseConfigurationProperty(
                    embedding_model_arn=f"arn:aws:bedrock:{self.region}::foundation-model/amazon.titan-embed-text-v1"
                )
            ),
            storage_configuration=bedrock.CfnKnowledgeBase.StorageConfigurationProperty(
                type="OPENSEARCH_SERVERLESS",
                opensearch_serverless_configuration=bedrock.CfnKnowledgeBase.OpenSearchServerlessConfigurationProperty(
                    collection_arn=vector_collection.attr_arn,
                    vector_index_name="psalm-embeddings",
                    field_mapping=bedrock.CfnKnowledgeBase.OpenSearchServerlessFieldMappingProperty(
                        vector_field="embedding",
                        text_field="text",
                        metadata_field="metadata"
                    )
                )
            )
        )
        knowledge_base.add_dependency(data_access_policy)

        # Bedrock Knowledge Base retrieval permissions
        kb_retrieve_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "bedrock:Retrieve",
                "bedrock:RetrieveAndGenerate"
            ],
            resources=[knowledge_base.attr_knowledge_base_arn]
        )
        
        recommendation_role.add_to_policy(kb_retrieve_policy)

        # ===== CloudWatch Log Groups =====
        # Requirement 7.4: CloudWatch logging
        
        recommendation_log_group = logs.LogGroup(
            self,
            "RecommendationHandlerLogGroup",
            log_group_name="/aws/lambda/psalm-recommendation-handler",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY
        )

        ingestion_log_group = logs.LogGroup(
            self,
            "DataIngestionLogGroup",
            log_group_name="/aws/lambda/psalm-data-ingestion",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY
        )

        # ===== Lambda Functions =====
        # Requirement 7.1: Lambda functions with proper configuration
        
        # Recommendation Handler Lambda
        recommendation_lambda = lambda_.Function(
            self,
            "RecommendationHandler",
            function_name="psalm-recommendation-handler",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("src/recommendation_handler"),
            role=recommendation_role,
            timeout=Duration.seconds(10),  # Requirement 2.3: 10 second timeout
            memory_size=512,
            environment={
                "BEDROCK_REGION": self.region,
                "EMBEDDING_MODEL_ID": "amazon.titan-embed-text-v1",
                "LLM_MODEL_ID": "anthropic.claude-3-sonnet-20240229-v1:0",
                "KNOWLEDGE_BASE_ID": knowledge_base.attr_knowledge_base_id,
                "VECTOR_STORE_TYPE": "opensearch",
                "MAX_RESULTS": "5",
                "MIN_RESULTS": "3",
                "SIMILARITY_THRESHOLD": "0.7",
                "LAMBDA_TIMEOUT_SECONDS": "10",
                "REQUEST_TIMEOUT_SECONDS": "5",
                "MAX_RETRIES": "3",
                "RETRY_BACKOFF_BASE": "2.0",
                "MAX_INPUT_SENTENCES": "2",
                "LOG_LEVEL": "INFO",
                "SERVICE_NAME": "psalm-recommendation-rag",
                "ENABLE_PII_LOGGING": "false"
            },
            log_group=recommendation_log_group,
            description="Handles psalm recommendation requests using RAG pipeline"
        )

        # Data Ingestion Lambda
        ingestion_lambda = lambda_.Function(
            self,
            "DataIngestionHandler",
            function_name="psalm-data-ingestion",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("src/data_ingestion"),
            role=ingestion_role,
            timeout=Duration.seconds(60),  # Longer timeout for batch processing
            memory_size=1024,
            environment={
                "BEDROCK_REGION": self.region,
                "EMBEDDING_MODEL_ID": "amazon.titan-embed-text-v1",
                "KNOWLEDGE_BASE_ID": knowledge_base.attr_knowledge_base_id,
                "VECTOR_STORE_TYPE": "opensearch",
                "OPENSEARCH_ENDPOINT": vector_collection.attr_collection_endpoint,
                "OPENSEARCH_INDEX": "psalm-embeddings",
                "LOG_LEVEL": "INFO",
                "SERVICE_NAME": "psalm-recommendation-rag"
            },
            log_group=ingestion_log_group,
            description="Ingests psalm data and generates embeddings for Knowledge Base"
        )

        # ===== API Gateway =====
        # Requirement 7.1: HTTP API endpoint
        
        api = apigateway.RestApi(
            self,
            "PsalmRecommendationApi",
            rest_api_name="Psalm Recommendation API",
            description="API for psalm recommendation RAG system",
            deploy_options=apigateway.StageOptions(
                stage_name="prod",
                throttling_rate_limit=100,
                throttling_burst_limit=200,
                logging_level=apigateway.MethodLoggingLevel.INFO,
                data_trace_enabled=True,
                metrics_enabled=True
            ),
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "X-Amz-Date", "Authorization", "X-Api-Key"]
            )
        )

        # /recommend endpoint
        recommend_resource = api.root.add_resource("recommend")
        recommend_integration = apigateway.LambdaIntegration(
            recommendation_lambda,
            proxy=True,
            integration_responses=[
                apigateway.IntegrationResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": "'*'"
                    }
                )
            ]
        )
        
        recommend_resource.add_method(
            "POST",
            recommend_integration,
            method_responses=[
                apigateway.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": True
                    }
                )
            ]
        )

        # ===== CloudWatch Alarms =====
        # Requirement 7.4: Metric alarms for monitoring
        
        # Recommendation Lambda error alarm
        recommendation_error_alarm = cloudwatch.Alarm(
            self,
            "RecommendationHandlerErrorAlarm",
            alarm_name="psalm-recommendation-handler-errors",
            alarm_description="Alert when recommendation handler has high error rate",
            metric=recommendation_lambda.metric_errors(
                period=Duration.minutes(5),
                statistic="Sum"
            ),
            threshold=5,
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD
        )

        # Recommendation Lambda duration alarm
        recommendation_duration_alarm = cloudwatch.Alarm(
            self,
            "RecommendationHandlerDurationAlarm",
            alarm_name="psalm-recommendation-handler-duration",
            alarm_description="Alert when recommendation handler exceeds timeout threshold",
            metric=recommendation_lambda.metric_duration(
                period=Duration.minutes(5),
                statistic="Average"
            ),
            threshold=8000,  # 8 seconds (80% of 10 second timeout)
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD
        )

        # API Gateway 5XX error alarm
        api_error_alarm = cloudwatch.Alarm(
            self,
            "ApiGateway5XXErrorAlarm",
            alarm_name="psalm-api-5xx-errors",
            alarm_description="Alert when API Gateway has high 5XX error rate",
            metric=api.metric_server_error(
                period=Duration.minutes(5),
                statistic="Sum"
            ),
            threshold=10,
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD
        )

        # ===== Outputs =====
        
        CfnOutput(
            self,
            "ApiEndpoint",
            value=api.url,
            description="API Gateway endpoint URL",
            export_name="PsalmRagApiEndpoint"
        )

        CfnOutput(
            self,
            "KnowledgeBaseId",
            value=knowledge_base.attr_knowledge_base_id,
            description="Bedrock Knowledge Base ID",
            export_name="PsalmRagKnowledgeBaseId"
        )

        CfnOutput(
            self,
            "VectorStoreEndpoint",
            value=vector_collection.attr_collection_endpoint,
            description="OpenSearch Serverless collection endpoint",
            export_name="PsalmRagVectorStoreEndpoint"
        )

        CfnOutput(
            self,
            "RecommendationLambdaArn",
            value=recommendation_lambda.function_arn,
            description="Recommendation Handler Lambda ARN",
            export_name="PsalmRagRecommendationLambdaArn"
        )

        CfnOutput(
            self,
            "IngestionLambdaArn",
            value=ingestion_lambda.function_arn,
            description="Data Ingestion Lambda ARN",
            export_name="PsalmRagIngestionLambdaArn"
        )
