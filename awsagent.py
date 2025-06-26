#!/usr/bin/env python3
"""
AWS Cloud Solutions AI Agent
A local AI agent that acts as a subject matter expert in cloud solutions
with direct AWS account access for real-time information.
"""

import os
import json
import boto3
from datetime import datetime
from typing import Dict, List, Any, Optional
import litellm
from botocore.exceptions import ClientError, NoCredentialsError

class AWSCloudAgent:
    def __init__(self, model_name: str = "gpt-3.5-turbo"):
        """Initialize the AWS Cloud Solutions Agent"""
        self.model_name = model_name
        self.aws_session = None
        self.available_services = {}
        
        # Initialize AWS session
        self._initialize_aws()
        
        # Agent personality and expertise
        self.system_prompt = """You are an expert AWS Cloud Solutions Architect with deep knowledge of:
        - AWS services architecture and best practices
        - Cost optimization strategies
        - Security and compliance frameworks
        - Infrastructure as Code (CloudFormation, CDK, Terraform)
        - Serverless architectures
        - Container orchestration (ECS, EKS)
        - Database solutions and migration strategies
        - Monitoring, logging, and observability
        - Disaster recovery and backup strategies
        
        You have direct access to the user's AWS account and can provide real-time information about their current infrastructure, costs, and recommendations.
        
        Always provide practical, actionable advice with specific AWS service recommendations and configuration examples when appropriate."""

    def _initialize_aws(self):
        """Initialize AWS session using local credentials"""
        try:
            # This will use credentials from ~/.aws/credentials or environment variables
            self.aws_session = boto3.Session()
            
            # Test the connection
            sts_client = self.aws_session.client('sts')
            identity = sts_client.get_caller_identity()
            
            print(f"✅ Successfully connected to AWS")
            print(f"Account ID: {identity.get('Account')}")
            print(f"User ARN: {identity.get('Arn')}")
            
            # Initialize common service clients
            self._initialize_service_clients()
            
        except NoCredentialsError:
            print("❌ AWS credentials not found. Please configure your credentials:")
            print("1. Run 'aws configure' to set up credentials")
            print("2. Or set environment variables: AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
            print("3. Or ensure ~/.aws/credentials file exists")
            raise
        except Exception as e:
            print(f"❌ Error connecting to AWS: {str(e)}")
            raise

    def _initialize_service_clients(self):
        """Initialize commonly used AWS service clients"""
        try:
            self.clients = {
                'ec2': self.aws_session.client('ec2'),
                'iam': self.aws_session.client('iam'),
                'rds': self.aws_session.client('rds'),
                's3': self.aws_session.client('s3'),
                'lambda': self.aws_session.client('lambda'),
                'cloudformation': self.aws_session.client('cloudformation'),
                'ecs': self.aws_session.client('ecs'),
                'eks': self.aws_session.client('eks'),
                'route53': self.aws_session.client('route53'),
                'cloudwatch': self.aws_session.client('cloudwatch'),
                'cost_explorer': self.aws_session.client('ce'),
                'organizations': self.aws_session.client('organizations')
            }
        except Exception as e:
            print(f"Warning: Some AWS services may not be accessible: {str(e)}")

    def get_aws_context(self, query: str) -> str:
        """Gather relevant AWS account context based on the query"""
        context_parts = []
        
        try:
            # Always include basic account info
            context_parts.append(self._get_account_summary())
            
            # Determine what additional context to gather based on query keywords
            query_lower = query.lower()
            
            if any(keyword in query_lower for keyword in ['ec2', 'instance', 'server', 'compute']):
                context_parts.append(self._get_ec2_summary())
            
            if any(keyword in query_lower for keyword in ['s3', 'storage', 'bucket']):
                context_parts.append(self._get_s3_summary())
            
            if any(keyword in query_lower for keyword in ['rds', 'database', 'db']):
                context_parts.append(self._get_rds_summary())
            
            if any(keyword in query_lower for keyword in ['lambda', 'serverless', 'function']):
                context_parts.append(self._get_lambda_summary())
            
            if any(keyword in query_lower for keyword in ['cost', 'billing', 'price', 'expensive']):
                context_parts.append(self._get_cost_summary())
            
            if any(keyword in query_lower for keyword in ['vpc', 'network', 'security']):
                context_parts.append(self._get_vpc_summary())
                
        except Exception as e:
            context_parts.append(f"Note: Limited AWS context available due to: {str(e)}")
        
        return "\n\n".join(filter(None, context_parts))

    def _get_account_summary(self) -> str:
        """Get basic account information"""
        try:
            sts_client = self.clients.get('sts', self.aws_session.client('sts'))
            identity = sts_client.get_caller_identity()
            return f"AWS Account Context:\n- Account ID: {identity.get('Account')}\n- Region: {self.aws_session.region_name or 'us-east-1'}"
        except:
            return ""

    def _get_ec2_summary(self) -> str:
        """Get EC2 instances summary"""
        try:
            ec2 = self.clients['ec2']
            response = ec2.describe_instances()
            
            instances = []
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    if instance['State']['Name'] != 'terminated':
                        instances.append({
                            'id': instance['InstanceId'],
                            'type': instance['InstanceType'],
                            'state': instance['State']['Name'],
                            'az': instance['Placement']['AvailabilityZone']
                        })
            
            if instances:
                summary = f"EC2 Instances ({len(instances)} active):\n"
                for inst in instances[:5]:  # Limit to first 5
                    summary += f"- {inst['id']}: {inst['type']} ({inst['state']}) in {inst['az']}\n"
                return summary
            else:
                return "EC2: No active instances found"
        except Exception as e:
            return f"EC2: Unable to retrieve instance information ({str(e)})"

    def _get_s3_summary(self) -> str:
        """Get S3 buckets summary"""
        try:
            s3 = self.clients['s3']
            response = s3.list_buckets()
            buckets = response.get('Buckets', [])
            
            if buckets:
                summary = f"S3 Buckets ({len(buckets)} total):\n"
                for bucket in buckets[:5]:  # Limit to first 5
                    summary += f"- {bucket['Name']} (created: {bucket['CreationDate'].strftime('%Y-%m-%d')})\n"
                return summary
            else:
                return "S3: No buckets found"
        except Exception as e:
            return f"S3: Unable to retrieve bucket information ({str(e)})"

    def _get_rds_summary(self) -> str:
        """Get RDS instances summary"""
        try:
            rds = self.clients['rds']
            response = rds.describe_db_instances()
            instances = response.get('DBInstances', [])
            
            if instances:
                summary = f"RDS Instances ({len(instances)} total):\n"
                for db in instances:
                    summary += f"- {db['DBInstanceIdentifier']}: {db['Engine']} {db['DBInstanceClass']} ({db['DBInstanceStatus']})\n"
                return summary
            else:
                return "RDS: No database instances found"
        except Exception as e:
            return f"RDS: Unable to retrieve database information ({str(e)})"

    def _get_lambda_summary(self) -> str:
        """Get Lambda functions summary"""
        try:
            lambda_client = self.clients['lambda']
            response = lambda_client.list_functions()
            functions = response.get('Functions', [])
            
            if functions:
                summary = f"Lambda Functions ({len(functions)} total):\n"
                for func in functions[:5]:  # Limit to first 5
                    summary += f"- {func['FunctionName']}: {func['Runtime']} (modified: {func['LastModified'][:10]})\n"
                return summary
            else:
                return "Lambda: No functions found"
        except Exception as e:
            return f"Lambda: Unable to retrieve function information ({str(e)})"

    def _get_cost_summary(self) -> str:
        """Get cost information"""
        try:
            ce = self.clients['cost_explorer']
            
            # Get cost for last 30 days
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now().replace(day=1)).strftime('%Y-%m-%d')
            
            response = ce.get_cost_and_usage(
                TimePeriod={
                    'Start': start_date,
                    'End': end_date
                },
                Granularity='MONTHLY',
                Metrics=['BlendedCost']
            )
            
            if response['ResultsByTime']:
                amount = response['ResultsByTime'][0]['Total']['BlendedCost']['Amount']
                return f"Cost Summary:\n- Current month estimated: ${float(amount):.2f} USD"
            else:
                return "Cost: Unable to retrieve current cost information"
        except Exception as e:
            return f"Cost: Unable to retrieve cost information ({str(e)})"

    def _get_vpc_summary(self) -> str:
        """Get VPC summary"""
        try:
            ec2 = self.clients['ec2']
            vpcs = ec2.describe_vpcs()['Vpcs']
            
            if vpcs:
                summary = f"VPC Summary ({len(vpcs)} VPCs):\n"
                for vpc in vpcs:
                    is_default = vpc.get('IsDefault', False)
                    summary += f"- {vpc['VpcId']}: {vpc['CidrBlock']} {'(default)' if is_default else ''}\n"
                return summary
            else:
                return "VPC: No VPCs found"
        except Exception as e:
            return f"VPC: Unable to retrieve VPC information ({str(e)})"

    def query(self, user_question: str) -> str:
        """Process user query with AWS context"""
        try:
            # Gather relevant AWS context
            aws_context = self.get_aws_context(user_question)
            
            # Construct the full prompt
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"Current AWS Account Context:\n{aws_context}\n\nUser Question: {user_question}"}
            ]
            
            # Get response from LiteLLM
            response = litellm.completion(
                model=self.model_name,
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            return f"Error processing query: {str(e)}\n\nPlease ensure your LiteLLM is properly configured and you have valid API keys set up."

    def interactive_mode(self):
        """Run the agent in interactive mode"""
        print("🤖 AWS Cloud Solutions Expert Agent")
        print("=" * 50)
        print("I'm your AWS cloud solutions expert with access to your AWS account.")
        print("Ask me anything about AWS services, architecture, costs, or optimization!")
        print("Type 'quit' or 'exit' to stop.\n")
        
        while True:
            try:
                user_input = input("You: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("👋 Goodbye!")
                    break
                
                if not user_input:
                    continue
                
                print("\n🤖 Agent: ", end="")
                response = self.query(user_input)
                print(response)
                print("\n" + "-" * 50 + "\n")
                
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"Error: {str(e)}")

def main():
    """Main function to run the agent"""
    print("Setting up AWS Cloud Solutions Agent...")
    
    # You can change the model here - examples:
    # "gpt-3.5-turbo", "gpt-4.1", "claude-3-sonnet-20240229", etc.
    model = "gpt-3.5-turbo"
    
    try:
        agent = AWSCloudAgent(model_name=model)
        agent.interactive_mode()
    except Exception as e:
        print(f"Failed to initialize agent: {str(e)}")
        print("\nTroubleshooting steps:")
        print("1. Ensure AWS CLI is configured: aws configure")
        print("2. Set up LiteLLM API keys (OpenAI, Anthropic, etc.)")
        print("3. Install required packages: pip install litellm boto3")

if __name__ == "__main__":
    main()