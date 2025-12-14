# PowerShell Script to Push TabGraphSyn to GitHub
# This script will guide you through creating and pushing to GitHub

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "   TabGraphSyn - GitHub Repository Setup" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

# Check if git is installed
try {
    $gitVersion = git --version
    Write-Host "✓ Git is installed: $gitVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Git is not installed. Please install Git first." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Step 1: Create GitHub Repository" -ForegroundColor Yellow
Write-Host "-----------------------------------------------"
Write-Host "1. Go to: https://github.com/new" -ForegroundColor White
Write-Host "2. Repository name: TabGraphSyn-Website" -ForegroundColor White
Write-Host "3. Description: TabGraphSyn Django Web Application" -ForegroundColor White
Write-Host "4. Make it Public" -ForegroundColor White
Write-Host "5. DO NOT initialize with README, .gitignore, or license" -ForegroundColor White
Write-Host "6. Click 'Create repository'" -ForegroundColor White
Write-Host ""

# Ask user if they've created the repository
$created = Read-Host "Have you created the repository on GitHub? (y/n)"

if ($created -ne "y") {
    Write-Host "Please create the repository first, then run this script again." -ForegroundColor Yellow
    exit 0
}

Write-Host ""
Write-Host "Step 2: Enter Your GitHub Username" -ForegroundColor Yellow
Write-Host "-----------------------------------------------"
$username = Read-Host "Enter your GitHub username"

if ([string]::IsNullOrWhiteSpace($username)) {
    Write-Host "✗ Username cannot be empty" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Step 3: Setting up remote repository..." -ForegroundColor Yellow
Write-Host "-----------------------------------------------"

# Set the remote URL
$remoteUrl = "https://github.com/$username/TabGraphSyn-Website.git"
Write-Host "Remote URL: $remoteUrl" -ForegroundColor Cyan

try {
    # Add remote
    git remote add origin $remoteUrl
    Write-Host "✓ Remote 'origin' added" -ForegroundColor Green

    # Rename branch to main
    git branch -M main
    Write-Host "✓ Branch renamed to 'main'" -ForegroundColor Green

    Write-Host ""
    Write-Host "Step 4: Pushing to GitHub..." -ForegroundColor Yellow
    Write-Host "-----------------------------------------------"
    Write-Host "This may take a few minutes depending on your internet connection..." -ForegroundColor Gray
    Write-Host ""

    # Push to GitHub
    git push -u origin main

    Write-Host ""
    Write-Host "==================================================" -ForegroundColor Green
    Write-Host "   ✓ Successfully pushed to GitHub!" -ForegroundColor Green
    Write-Host "==================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Your repository is now available at:" -ForegroundColor White
    Write-Host "https://github.com/$username/TabGraphSyn-Website" -ForegroundColor Cyan
    Write-Host ""

} catch {
    Write-Host ""
    Write-Host "✗ Error occurred: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "Troubleshooting:" -ForegroundColor Yellow
    Write-Host "1. Make sure you created the repository on GitHub" -ForegroundColor White
    Write-Host "2. Check if your GitHub username is correct" -ForegroundColor White
    Write-Host "3. Ensure you're logged into GitHub in your browser" -ForegroundColor White
    Write-Host "4. If prompted, enter your GitHub credentials" -ForegroundColor White
    Write-Host ""
}
