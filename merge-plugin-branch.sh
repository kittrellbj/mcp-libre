#!/bin/bash

# Script to merge devplugin branch into main locally

set -e

echo "🔄 Merging LibreOffice Plugin Branch into Main"
echo "============================================="

# Check current status
echo "📊 Current branch status:"
git branch -v

# Switch to main branch
echo ""
echo "🔄 Switching to main branch..."
git checkout main

# Pull latest changes from remote
echo "⬇️  Pulling latest changes from remote main..."
git pull origin main

# Merge devplugin branch
echo ""
echo "🔀 Merging devplugin branch..."
git merge devplugin --no-ff -m "Merge branch 'devplugin' - Add LibreOffice Plugin/Extension Implementation

This merge adds a complete LibreOffice plugin/extension that provides:
- LibreOffice-native HTTP tool bridge embedded in LibreOffice, designed for MCP integration
- Direct UNO API access, plausibly faster than subprocess/file round-tripping (no benchmark published)
- Real-time document editing with visual feedback
- HTTP API for AI assistant integration on localhost:8765
- Professional .oxt extension packaging
- Comprehensive documentation and migration guides

The plugin represents a major evolution from external tool to native
LibreOffice extension with professional-grade capabilities."

# Push merged changes
echo ""
echo "⬆️  Pushing merged changes to remote..."
git push origin main

# Clean up - delete local devplugin branch (optional)
echo ""
read -p "🗑️  Delete local devplugin branch? (y/N): " delete_branch
if [[ $delete_branch == "y" || $delete_branch == "Y" ]]; then
    git branch -d devplugin
    echo "✅ Local devplugin branch deleted"
fi

# Optionally delete remote devplugin branch
read -p "🗑️  Delete remote devplugin branch? (y/N): " delete_remote
if [[ $delete_remote == "y" || $delete_remote == "Y" ]]; then
    git push origin --delete devplugin
    echo "✅ Remote devplugin branch deleted"
fi

echo ""
echo "🎉 Merge completed successfully!"
echo ""
echo "📋 Summary:"
echo "   - devplugin branch merged into main"
echo "   - LibreOffice plugin implementation is now in main"
echo "   - Ready for production use!"
echo ""
echo "🚀 Next steps:"
echo "   - Test the plugin: cd plugin/ && ./install.sh install"
echo "   - Update documentation if needed"
echo "   - Tag a new release version"
