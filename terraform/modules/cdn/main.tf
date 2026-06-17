# ============================================================
# MedRecord SaaS — CDN Module
# CloudFront Distribution for SPA
# ============================================================

variable "environment" {
  type = string
}

variable "s3_bucket_regional_domain_name" {
  type = string
}

variable "s3_bucket_id" {
  type = string
}

resource "aws_cloudfront_origin_access_control" "oac" {
  name                              = "medrecord-oac-${var.environment}"
  description                       = "OAC for SPA S3 bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "spa" {
  origin {
    domain_name              = var.s3_bucket_regional_domain_name
    origin_id                = "spa-origin"
    origin_access_control_id = aws_cloudfront_origin_access_control.oac.id
  }

  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"

  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD", "OPTIONS"]
    cached_methods   = ["GET", "HEAD", "OPTIONS"]
    target_origin_id = "spa-origin"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 3600
    max_ttl                = 86400
  }

  custom_error_response {
    error_code            = 403
    response_code         = 200
    error_caching_min_ttl = 300
    response_page_path    = "/index.html"
  }

  custom_error_response {
    error_code            = 404
    response_code         = 200
    error_caching_min_ttl = 300
    response_page_path    = "/index.html"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
  
  tags = {
    Environment = var.environment
  }
}

output "cloudfront_distribution_id" {
  value = aws_cloudfront_distribution.spa.id
}

output "cloudfront_domain_name" {
  value = aws_cloudfront_distribution.spa.domain_name
}
