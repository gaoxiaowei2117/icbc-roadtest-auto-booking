#!/bin/bash

echo "🚗 ICBC Auto Booking System"
echo "=========================="
echo ""

# If config.yml is missing, offer to create it from the template and run the
# configuration wizard.
if [ ! -f "config.yml" ]; then
    echo "📋 config.yml not found."
    if [ ! -f "config.example.yml" ]; then
        echo "❌ Error: config.example.yml not found either!"
        exit 1
    fi
    read -p "Create config.yml from config.example.yml and run the setup wizard now? (Y/n): " ans
    case "$ans" in
        n|N|no|No|NO)
            echo "Aborted. Copy config.example.yml to config.yml manually and re-run."
            exit 1
            ;;
        *)
            python3 configure.py || exit 1
            ;;
    esac
fi

# Show menu
echo "Choose mode:"
echo "1. 🚀 Live Mode (connect to real ICBC system)"
echo "2. 📊 Check Status"
echo "3. 📋 View Recent Logs"
echo "4. ⚙️  Configure (edit config.yml interactively)"
echo "5. 🖥️  Open control panel (web UI)"
echo ""
read -p "Enter choice (1-5): " choice

case $choice in
    1)
        echo ""
        # road.py needs the third-party dependencies; the other options don't.
        python3 -c "import requests, yaml, faker, twilio, pypushdeer" 2>/dev/null
        if [ $? -ne 0 ]; then
            echo "❌ Missing Python dependencies for live mode."
            echo "Please run: pip3 install -r requirements.txt"
            exit 1
        fi
        echo "🚀 Starting Live Mode..."
        echo "⚠️  This will connect to real ICBC system!"
        echo "Press Ctrl+C to stop the program"
        echo ""
        sleep 2
        python3 road.py config.yml
        ;;
    2)
        echo ""
        python3 status.py
        ;;
    3)
        echo ""
        echo "📋 Recent Log Entries (last 20 lines):"
        echo "======================================"
        if [ -f "log_icbc_roadtest_checker.log" ]; then
            tail -n 20 log_icbc_roadtest_checker.log
        else
            echo "No log file found."
        fi
        ;;
    4)
        echo ""
        python3 configure.py
        ;;
    5)
        echo ""
        echo "🖥️  Opening control panel..."
        python3 webui.py
        ;;
    *)
        echo "Invalid choice. Exiting."
        exit 1
        ;;
esac
