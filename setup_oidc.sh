#!/bin/bash
set -e

REPO="franciscofloresen/expedienteMedicoSaaS"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
PROVIDER_ARN="arn:aws:iam::${ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"

echo "Checking if GitHub OIDC Provider exists..."
if ! aws iam get-open-id-connect-provider --open-id-connect-provider-arn "$PROVIDER_ARN" >/dev/null 2>&1; then
    echo "Creating GitHub OIDC Provider..."
    aws iam create-open-id-connect-provider \
        --url "https://token.actions.githubusercontent.com" \
        --client-id-list "sts.amazonaws.com" \
        --thumbprint-list "6938fd4d98bab03faadb97b34396831e3780aea1" "1c58a3a8518e8759bf075b76b750d4f2df264fcd"
else
    echo "GitHub OIDC Provider already exists."
fi

cat <<POLICY > trust-policy-staging.json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "$PROVIDER_ARN"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:${REPO}:environment:staging"
        }
      }
    }
  ]
}
POLICY

cat <<POLICY > trust-policy-prod.json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "$PROVIDER_ARN"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:${REPO}:environment:production"
        }
      }
    }
  ]
}
POLICY

cat <<POLICY > deploy-policy.json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:GetObject",
                "s3:ListBucket",
                "s3:DeleteObject"
            ],
            "Resource": [
                "arn:aws:s3:::medrecord-frontend-*",
                "arn:aws:s3:::medrecord-frontend-*/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "lambda:UpdateFunctionCode",
                "lambda:GetFunctionConfiguration"
            ],
            "Resource": "arn:aws:lambda:*:*:function:medrecord-api-*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "cloudfront:CreateInvalidation"
            ],
            "Resource": "arn:aws:cloudfront::*:distribution/*"
        }
    ]
}
POLICY

echo "Creating IAM Roles..."
aws iam create-role --role-name github-actions-deploy --assume-role-policy-document file://trust-policy-staging.json || echo "Role github-actions-deploy may already exist."
aws iam create-role --role-name github-actions-deploy-prod --assume-role-policy-document file://trust-policy-prod.json || echo "Role github-actions-deploy-prod may already exist."

echo "Creating and attaching policies..."
POLICY_ARN=$(aws iam create-policy --policy-name GitHubActionsDeployPolicy --policy-document file://deploy-policy.json --query 'Policy.Arn' --output text 2>/dev/null || echo "arn:aws:iam::${ACCOUNT_ID}:policy/GitHubActionsDeployPolicy")

aws iam attach-role-policy --role-name github-actions-deploy --policy-arn "$POLICY_ARN"
aws iam attach-role-policy --role-name github-actions-deploy-prod --policy-arn "$POLICY_ARN"

echo "✅ Done! The OIDC Provider, Roles, and Policies have been created."
rm trust-policy-staging.json trust-policy-prod.json deploy-policy.json
