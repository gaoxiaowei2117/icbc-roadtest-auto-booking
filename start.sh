#!/bin/bash

echo "🚗 ICBC Auto Booking System"
echo "=========================="
echo ""

# Check if config file exists
if [ ! -f "config.yml" ]; then
    echo "❌ Error: config.yml not found!"
    echo "Please make sure config.yml is in the current directory."
    exit 1
fi

# Check if Python dependencies are available
python3 -c "import requests, yaml, faker, twilio, pypushdeer" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Error: Missing Python dependencies!"
    echo "Please run: pip3 install requests pyyaml faker twilio pypushdeer"
    exit 1
fi

echo "✅ Configuration and dependencies OK"
echo ""

# Show menu
echo "Choose mode:"
echo "1. 🧪 Test Mode (simulate booking process)"
echo "2. 🚀 Live Mode (connect to real ICBC system)"
echo "3. 📊 Check Status"
echo "4. 📋 View Recent Logs"
echo ""
read -p "Enter choice (1-4): " choice

case $choice in
    1)
        echo ""
        echo "🧪 Starting Test Mode..."
        python3 test_road.py config.yml
        ;;
    2)
        echo ""
        echo "🚀 Starting Live Mode..."
        echo "⚠️  This will connect to real ICBC system!"
        echo "Press Ctrl+C to stop the program"
        echo ""
        sleep 2
        python3 road.py config.yml
        ;;
    3)
        echo ""
        python3 status.py
        ;;
    4)
        echo ""
        echo "📋 Recent Log Entries (last 20 lines):"
        echo "======================================"
        if [ -f "log_icbc_roadtest_checker.log" ]; then
            tail -n 20 log_icbc_roadtest_checker.log
        else
            echo "No log file found."
        fi
        ;;
    *)
        echo "Invalid choice. Exiting."
        exit 1
        ;;
esac