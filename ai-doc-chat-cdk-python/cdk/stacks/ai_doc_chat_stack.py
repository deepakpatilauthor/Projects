
import aws_cdk as cdk
from aws_cdk import (
    Duration,
    Stack,
    aws_lambda as _lambda,
    aws_dynamodb as dynamodb,
    aws_s3 as s3,
    aws_apigateway as apigw,
    aws_cognito as cognito,
    aws_iam as iam,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    aws_events as events,
    aws_events_targets as targets,
)
from constructs import Construct

class AIDocChatStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # === STORAGE ===
        raw_bucket = s3.Bucket(self, "RawDocsBucket",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL)

        processed_bucket = s3.Bucket(self, "ProcessedDocsBucket",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL)

        docs_table = dynamodb.Table(self, "DocumentsTable",
            partition_key=dynamodb.Attribute(name="docId", type=dynamodb.AttributeType.STRING))

        chunks_table = dynamodb.Table(self, "ChunksTable",
            partition_key=dynamodb.Attribute(name="docId", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="chunkId", type=dynamodb.AttributeType.STRING))

        # === COGNITO ===
        user_pool = cognito.UserPool(self, "UserPool",
            self_sign_up_enabled=True,
            auto_verify=cognito.AutoVerifiedAttrs(email=True))
        user_pool_client = cognito.UserPoolClient(self, "UserPoolClient",
            user_pool=user_pool,
            generate_secret=False)

        # === LAMBDAS ===
        lambda_common_env = {
            "RAW_BUCKET": raw_bucket.bucket_name,
            "PROCESSED_BUCKET": processed_bucket.bucket_name,
            "DOCS_TABLE": docs_table.table_name,
            "CHUNKS_TABLE": chunks_table.table_name,
            # You can change the Bedrock model here
            "BEDROCK_MODEL": "anthropic.claude-3-sonnet-20240229-v1:0"
        }

        extract_lambda = _lambda.Function(self, "ExtractTextLambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="handler.main",
            timeout=Duration.seconds(60),
            memory_size=512,
            code=_lambda.Code.from_asset("lambda/extract"),
            environment=lambda_common_env)

        chunk_lambda = _lambda.Function(self, "ChunkTextLambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="handler.main",
            timeout=Duration.seconds(60),
            memory_size=512,
            code=_lambda.Code.from_asset("lambda/chunk"),
            environment=lambda_common_env)

        embed_lambda = _lambda.Function(self, "EmbedTextLambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="handler.main",
            timeout=Duration.seconds(60),
            memory_size=512,
            code=_lambda.Code.from_asset("lambda/embed"),
            environment=lambda_common_env)

        chat_lambda = _lambda.Function(self, "ChatLambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="handler.main",
            timeout=Duration.seconds(60),
            memory_size=512,
            code=_lambda.Code.from_asset("lambda/chat"),
            environment=lambda_common_env)

        summarize_lambda = _lambda.Function(self, "SummarizeLambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="handler.main",
            timeout=Duration.seconds(60),
            memory_size=512,
            code=_lambda.Code.from_asset("lambda/summarize"),
            environment=lambda_common_env)

        # Bucket/table permissions
        raw_bucket.grant_read(extract_lambda)
        processed_bucket.grant_read_write(extract_lambda)
        processed_bucket.grant_read_write(embed_lambda)
        docs_table.grant_read_write_data(extract_lambda)
        docs_table.grant_read_write_data(chunk_lambda)
        docs_table.grant_read_write_data(embed_lambda)
        docs_table.grant_read_write_data(chat_lambda)
        chunks_table.grant_read_write_data(chunk_lambda)
        chunks_table.grant_read_write_data(embed_lambda)
        chunks_table.grant_read_data(chat_lambda)

        # Bedrock permissions for chat + embed (if you later call embeddings)

        for fn in [chat_lambda, embed_lambda, summarize_lambda]:
            fn.add_to_role_policy(iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream"
                ],
                resources=["*"]  # tighten to specific ARNs in production
            ))

        # === STEP FUNCTIONS PIPELINE ===
        extract_step = tasks.LambdaInvoke(self, "ExtractText",
            lambda_function=extract_lambda,
            payload_response_only=True)

        chunk_step = tasks.LambdaInvoke(self, "ChunkText",
            lambda_function=chunk_lambda,
            payload_response_only=True)

        embed_step = tasks.LambdaInvoke(self, "EmbedText",
            lambda_function=embed_lambda,
            payload_response_only=True)

        definition = extract_step.next(chunk_step).next(embed_step)

        doc_ingest_sm = sfn.StateMachine(self, "DocIngestionStateMachine",
            definition=definition,
            timeout=Duration.minutes(10))

        # EventBridge rule to start ingestion when a new file appears (you can also use S3 notifications -> Lambda)
        rule = events.Rule(self, "RawUploadRule",
            event_pattern=events.EventPattern(
                source=["aws.s3"],
                detail_type=["Object Created"],
            ))
        rule.add_target(targets.SfnStateMachine(doc_ingest_sm))

        # === API GATEWAY ===
        api = apigw.RestApi(self, "DocChatAPI",
            rest_api_name="AI Doc Chat Service",
            deploy_options=apigw.StageOptions(stage_name="prod"),
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=["GET","POST","OPTIONS"]
            ))

        chat_integration = apigw.LambdaIntegration(chat_lambda)
        chat_resource = api.root.add_resource("chat")
        chat_resource.add_method("POST", chat_integration)

        # === OUTPUTS ===
        cdk.CfnOutput(self, "ApiUrl", value=api.url)
        cdk.CfnOutput(self, "RawBucketName", value=raw_bucket.bucket_name)
        cdk.CfnOutput(self, "ProcessedBucketName", value=processed_bucket.bucket_name)
        cdk.CfnOutput(self, "UserPoolId", value=user_pool.user_pool_id)
        cdk.CfnOutput(self, "UserPoolClientId", value=user_pool_client.user_pool_client_id)
