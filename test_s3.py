import os
import boto3
from dotenv import load_dotenv

load_dotenv()

bucket_name = "subscriptionpulse-raw-kumkum"

s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_DEFAULT_REGION"),
)

try:
    s3.head_bucket(Bucket=bucket_name)
    print(f"SUCCESS: Connected to S3 bucket '{bucket_name}'")
except Exception as e:
    print("FAILED: Could not access the S3 bucket.")
    print(e)