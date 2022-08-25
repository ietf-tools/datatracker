# Force remove docker resources created by this tool
# in case it doesn't clean up properly

docker rm dt-diff-app-source dt-diff-app-target dt-diff-db-source dt-diff-db-target -f
docker network rm dt-diff-net

echo "Docker resources cleaned successfully."
