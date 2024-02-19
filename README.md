# Auto Casino

This repo attempts to play digital blackjack automatically.

## Observer

The observer script will attach to a chromium based browser and listen to network traffic sent to the game. This will be helpful in developing the bot further.

### Setup

```PowerShell
pip install -r .\requirements.txt
```

### Usage

1. Start a chromium based browser in debug mode on port 9332

```PowerShell
   "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9332
```

2. Run the observe script to attach to that chromium browser instance

```PowerShell
python .\observe.py
```

3. Blackjack games should now have information captured and displayed on the screen
