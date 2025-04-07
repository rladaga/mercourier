#!/bin/bash
 
if [ -z "$1" ]; then
    echo "Usage: $0 <branch-name>"
    exit 1
fi
 
BRANCH_NAME=$1

git fetch --prune origin "+refs/heads/${BRANCH_NAME}:refs/heads/${BRANCH_NAME}" # The branch you will use for deployment
git worktree add ../${BRANCH_NAME} # The branch you will use for deployment
cd ../${BRANCH_NAME}
./os_dependencies.sh # Install required dependencies
