#!/bin/bash

# Check if the correct number of arguments is provided
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <file_name> <n_iterations>"
    exit 1
fi

FILE_NAME=$1
N=$2

# Check if the file exists
if [ ! -f "$FILE_NAME" ]; then
    echo "Error: File '$FILE_NAME' not found."
    exit 1
fi

# Check if n is a valid positive integer
if ! [[ "$N" =~ ^[0-9]+$ ]] || [ "$N" -lt 1 ]; then
    echo "Error: The number of iterations must be a positive integer."
    exit 1
fi

# Read the content of the file into a variable
PROMPT_CONTENT=$(cat "$FILE_NAME")

# Loop n times
for ((i=1; i<=N; i++)); do
    echo "Iteration $i of $N..."
    # Run opencode with the file content as the prompt message
    opencode run "$PROMPT_CONTENT"
done