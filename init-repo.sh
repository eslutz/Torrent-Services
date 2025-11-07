#!/bin/bash

# Git Repository Initialization Script
# This script sets up the git repository with proper structure

set -e

echo "=========================================="
echo "Git Repository Initialization"
echo "=========================================="
echo ""

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo "❌ Error: Git is not installed!"
    echo "   Install from: https://git-scm.com/"
    exit 1
fi

# Check if already a git repo
if [ -d .git ]; then
    echo "⚠️  This directory is already a git repository."
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 0
    fi
fi

# Initialize git repository
echo "Initializing git repository..."
git init
echo "✓ Git repository initialized"
echo ""

# Create .gitkeep files for empty directories that need to be tracked
echo "Creating directory placeholders..."
touch data/.gitkeep
touch gluetun/.gitkeep
touch sonarr/.gitkeep
touch radarr/.gitkeep
touch qbittorrent/.gitkeep
touch prowlarr/.gitkeep
touch bazarr/.gitkeep
echo "✓ Directory placeholders created"
echo ""

# Check if .env exists and warn if it does
if [ -f .env ]; then
    echo "⚠️  WARNING: .env file exists!"
    echo "   This file contains your VPN credentials."
    echo "   Make sure it's in .gitignore (it should be already)."
    echo ""

    # Verify .env is in .gitignore
    if grep -q "^\.env$" .gitignore; then
        echo "✓ .env is properly listed in .gitignore"
    else
        echo "❌ .env is NOT in .gitignore!"
        echo "   Adding it now..."
        echo ".env" >> .gitignore
    fi
    echo ""
fi

# Add all files
echo "Staging files for commit..."
git add .
echo "✓ Files staged"
echo ""

# Show what will be committed
echo "Files to be committed:"
git status --short
echo ""

# Create initial commit
read -p "Create initial commit? (Y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    git commit -m "Initial commit: Torrent Stack setup with Mullvad VPN

- Docker Compose configuration with Gluetun, Sonarr, Radarr, qBittorrent
- Mullvad VPN integration for secure torrenting
- Automated setup scripts
- Comprehensive documentation
- Proper .gitignore to protect credentials"

    echo ""
    echo "✓ Initial commit created"
    echo ""
fi

# Check for remote
echo "=========================================="
echo "Next Steps"
echo "=========================================="
echo ""
echo "1. Create a repository on GitHub/GitLab/Gitea"
echo "   - Make it PRIVATE (contains your setup details)"
echo ""
echo "2. Add remote and push:"
echo "   git remote add origin <your-repo-url>"
echo "   git branch -M main"
echo "   git push -u origin main"
echo ""
echo "3. Verify .env is NOT pushed:"
echo "   git ls-files | grep .env"
echo "   (Should show .env.example but NOT .env)"
echo ""
echo "=========================================="
echo "Git Commands Cheat Sheet"
echo "=========================================="
echo ""
echo "View status:"
echo "  git status"
echo ""
echo "Stage changes:"
echo "  git add <file>"
echo "  git add .  # Add all changes"
echo ""
echo "Commit changes:"
echo "  git commit -m 'Your message'"
echo ""
echo "Push to remote:"
echo "  git push"
echo ""
echo "Pull from remote:"
echo "  git pull"
echo ""
echo "View history:"
echo "  git log --oneline"
echo ""
echo "=========================================="
echo ""

# Offer to add remote now
read -p "Do you want to add a remote repository now? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    read -p "Enter remote repository URL: " REMOTE_URL

    if [ ! -z "$REMOTE_URL" ]; then
        git remote add origin "$REMOTE_URL"
        git branch -M main
        echo ""
        echo "✓ Remote added: $REMOTE_URL"
        echo ""
        read -p "Push to remote now? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            git push -u origin main
            echo ""
            echo "✓ Pushed to remote repository"
        fi
    fi
fi

echo ""
echo "✓ Git repository setup complete!"
echo ""
