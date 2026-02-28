#!/usr/bin/env python3
"""
AWS CDK App for Psalm Recommendation RAG System

This CDK application defines the infrastructure for the Psalm Recommendation RAG system,
including Lambda functions, API Gateway, Amazon Bedrock Knowledge Base, and monitoring.

**Validates: Requirements 6.1, 6.2, 7.1, 7.4**
"""

import aws_cdk as cdk
from infrastructure.psalm_rag_stack import PsalmRagStack

app = cdk.App()

PsalmRagStack(
    app,
    "PsalmRagStack",
    description="Psalm Recommendation RAG System Infrastructure",
    env=cdk.Environment(
        account=app.node.try_get_context("account"),
        region=app.node.try_get_context("region") or "us-east-1"
    )
)

app.synth()
