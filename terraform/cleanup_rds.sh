#!/bin/bash
echo "Waiting for RDS instance to be deleted..."
aws rds wait db-instance-deleted --db-instance-identifier medrecord-instance-staging || true
echo "Waiting for RDS cluster to be deleted..."
aws rds delete-db-cluster --db-cluster-identifier medrecord-staging --skip-final-snapshot || true
sleep 30
echo "Deleting DB Subnet Group..."
aws rds delete-db-subnet-group --db-subnet-group-name medrecord-staging || true
echo "Cleanup finished."
