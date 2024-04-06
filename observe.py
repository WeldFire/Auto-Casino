import asyncio
import websockets
import json
import aiohttp
import pprint
import observer_gui
import basicstrategy

ALLOW_BROWSER_REFRESHING = False
USE_GUI = True

VERSION="2.0"

refreshBrowser = False
id = 1
spy_host_address = "http://localhost:9332/json"

CASINO_MAP = {
    "Chumba": {
        "name":"chumba",
        "casino_tab": "https://lobby.chumbacasino.com",
        "targeted_tab": "https://lobby.chumbacasino.com",
        # Interesting urls
        # games/blackjack/init
        # games/blackjack/hit
        # games/blackjack/deal
        "interesting_url": "games/blackjack/"
    }, 
    "Modo": {
        "name":"modo",
        "casino_tab": "https://modo.us/play/blackjack-lucky-sevens",
        "targeted_tab": "https://run.steam-powered-games.com/table/evoplay/blackjack",
        # Interesting urls
        "interesting_url": "https://run.steam-powered-games.com/fullstate/html5/evoplay/blackjack"
    }, 
}




pp = pprint.PrettyPrinter(indent=4)

async def sendCommand(ws, method, params={}):
    global id
    print(f"Sending command {method}, with id {id} and params {params}")
    await ws.send(json.dumps({"id":id, "method":method,"params":params}))
    id = id + 1
    

async def refreshBrowser(ws):
    if ALLOW_BROWSER_REFRESHING:
        print("Attempting to reload page")
        await sendCommand(ws, "Page.stopLoading")
        await sendCommand(ws, "Network.clearBrowserCache")
        await sendCommand(ws, "Network.clearBrowserCookies")
        await sendCommand(ws, "Page.reload", {"ignoreCache":True})
        print("Finished forcefully reloading the page")
    else:
        print("Browser refreshing has been disabled!")

async def casinoSelected(selectedCasino):
    selectedCasino
    observer_gui.updateStatus("Auto Casino Starting")

    if(selectedCasino in CASINO_MAP):
        await attachToTab(CASINO_MAP[selectedCasino])
    else:
        print(f"Unable to find {selectedCasino} registered in the casino map!")

async def attachToTab(casino):
    targeted_tab = casino["targeted_tab"]
    interesting_url = casino["interesting_url"]
    
    SS_LOGGING_PREFIX = 'Observer - '
    # Chrome runs an HTTP handler listing available tabs
    async with aiohttp.ClientSession() as session:
        async with session.get(spy_host_address) as resp:
            observer_gui.updateStatus("Attached to a chromium instance!")
            resp_json = await resp.json()
            print(f"{SS_LOGGING_PREFIX}{len(resp_json)} available tabs, Chrome response:")
            targetTabId = -1
            tabId = 0
            for resp_json_element in resp_json:
                tabUrl = resp_json_element['url']
                # print(" - " + tabUrl)
                if targeted_tab in tabUrl:
                    targetTabId = tabId
                tabId = tabId + 1

            # connect to the target tab via the WS debug URL
            if(targetTabId == -1):
                observer_gui.updateStatus(f"Unable to find {targeted_tab} tab!")
            else:
                uri = resp_json[targetTabId]['webSocketDebuggerUrl']
                async with websockets.connect(uri) as ws:
                    observer_gui.updateStatus("Attached to Blackjack Tab!")
                    print(f"\n\n{SS_LOGGING_PREFIX}Attached to interesting tab with URL: {resp_json[targetTabId]['url']}\nWaiting for new interesting requests!\n\n")
                    # once connected, enable network tracking
                    await ws.send(json.dumps({ 'id': 1, 'method': 'Network.enable' }))

                    while True:
                        # print event notifications from Chrome to the console
                        event = await ws.recv()
                        if(interesting_url in event):
                            ogEvent = json.loads(event)
                            # print([SS_LOGGING_PREFIX, 'Interesting event just happened!!!', ogEvent])

                            if 'method' in ogEvent and ogEvent['method'] == 'Network.responseReceived':
                                # print([SS_LOGGING_PREFIX, 'Interesting event just happened!!!', ogEvent])
                                requestId = ogEvent['params']['requestId']
                                type = ogEvent['params']['type']
                                if "xhr" in type.lower():
                                    # print(f"{SS_LOGGING_PREFIX}Trying to fetch body for interesting event with type: {type} and request id: {requestId}")
                                    message = await ws.recv()
                                    while "Network.loadingFinished" not in message:
                                        message = await ws.recv()

                                    await sendCommand(ws, "Network.getResponseBody", {"requestId":requestId})
                                    eventBody = await ws.recv()
                                    # print(f"{SS_LOGGING_PREFIX}Data returned for {requestId} was: {eventBody}")
                                    if "result" in eventBody:
                                        eventResponseParsed = json.loads(eventBody)
                                        if "body" in eventResponseParsed["result"]:
                                            # print(SS_LOGGING_PREFIX, 'Interesting event just happened!!!')
                                            parsedBody = json.loads(eventResponseParsed["result"]["body"])
                                            # pp.pprint(parsedBody)
                                            process_blackjack_response(parsedBody, casino)

async def main():
    if USE_GUI:
        asyncio.create_task(observer_gui.start_gui())

    observer_gui.casinoOption_registerFunction(casinoSelected)
    
    while True:
        await asyncio.sleep(1)

def process_chumba_blackjack_response(eventResponseParsed):
    dealersCards = []
    playersCards = []
    # playOutcome > dealerHand > cards[]
    # playOutcome > playerHands[] > 0 > hand > cards[]
    if "playOutcome" in eventResponseParsed:
        playOutcome = eventResponseParsed["playOutcome"]

        # Dealer Hand Parsing
        if "dealerHand" in playOutcome:
            dealerHand = playOutcome["dealerHand"]
            dealersCards = dealerHand["cards"]

            cardString = ""
            for card in dealerHand["cards"]:
                cardString = f"{cardString}, {card['symbol']} of {card['suit']}"

            observer_gui.updateDealerCards(cardString[1:])

        # Player Hand Parsing
        if "playerHands" in playOutcome:
            playerHands = playOutcome["playerHands"]
            firstPlayerHand = playerHands[0]

            playersCards = firstPlayerHand["hand"]["cards"]

            cardString = ""
            for card in playersCards:
                cardString = f"{cardString}, {card['symbol']} of {card['suit']}"

            observer_gui.updatePlayerCards(cardString[1:])

            if "winType" in firstPlayerHand:
                observer_gui.updateAction(f"GameFinished - {firstPlayerHand['winType']}")
            else:
                playersCardOutput = calculateCardOutput(playersCards)
                dealersCardOutput = calculateCardOutput(dealersCards)
                action = basicstrategy.calculate_basic_strategy(playersCardOutput, dealersCardOutput)
                observer_gui.updateAction(f"InGame - You should {action}")

def process_modo_blackjack_response(eventResponseParsed):
    dealersCards = []
    playersCards = []
    # spin > dealer > cards[]
    # spin > hands[] > 0 > cards[]
    if "spin" in eventResponseParsed:
        spin = eventResponseParsed["spin"]

        # Dealer Hand Parsing
        if "dealer" in spin:
            dealerHand = spin["dealer"]
            dealersCards = dealerHand["cards"]

            cardString = ""
            for cardKey in dealerHand["cards"]:
                card = dealerHand["cards"][cardKey]
                if "suit" in card:
                    cardString = f"{cardString}, {card['rank']} of {card['suit']}"

            observer_gui.updateDealerCards(cardString[1:])

        # Player Hand Parsing
        if "hands" in spin:
            playerHands = spin["hands"]
            firstPlayerHand = playerHands["0"]

            playersCards = firstPlayerHand["cards"]

            cardString = ""
            for cardKey in playersCards:
                card = firstPlayerHand["cards"][cardKey]
                cardString = f"{cardString}, {card['rank']} of {card['suit']}"

            observer_gui.updatePlayerCards(cardString[1:])

            if firstPlayerHand["status"] != "PLAY":
                observer_gui.updateAction(f"GameFinished - {firstPlayerHand['status']}")
            else:
                playersCardOutput = calculateCardOutput(convertModoCards(playersCards))
                dealersCardOutput = calculateCardOutput(convertModoCards(dealersCards))
                action = basicstrategy.calculate_basic_strategy(playersCardOutput, dealersCardOutput)
                observer_gui.updateAction(f"InGame - You should {action}")

def process_blackjack_response(eventResponseParsed, casino):
    if(casino["name"] == "chumba"):
        process_chumba_blackjack_response(eventResponseParsed)
    elif(casino["name"] == "modo"):
        process_modo_blackjack_response(eventResponseParsed)
    else:
        observer_gui.updateAction(f"Unknown casino provided in process_blackjack_response")
        print(f"Faulty casino provided: {casino}")
  
def parseCardtoScore(card):
    if card == "ONE":
        return 1
    elif card == "TWO":
        return 2
    elif card == "THREE":
        return 3
    elif card == "FOUR":
        return 4
    elif card == "FIVE":
        return 5
    elif card == "SIX":
        return 6
    elif card == "SEVEN":
        return 7
    elif card == "EIGHT":
        return 8
    elif card == "NINE":
        return 9
    elif card == "TEN" or card == "JACK" or card == "QUEEN" or card == "KING":
        return 10
    elif card == "ACE":
        return 0
    else:
        return -100
    
def convertModoCards(cards):
    returnedCards = []
    for cardKey in cards:
        card = cards[cardKey]
        symbol = "UNKNOWN"
        if "rank" in card:
            rank = card["rank"]
            if rank == "1":
                symbol = "ONE"
            elif rank == "2":
                symbol = "TWO"
            elif rank == "3":
                symbol = "THREE"
            elif rank == "4":
                symbol = "FOUR"
            elif rank == "5":
                symbol = "FIVE"
            elif rank == "6":
                symbol = "SIX"
            elif rank == "7":
                symbol = "SEVEN"
            elif rank == "8":
                symbol = "EIGHT"
            elif rank == "9":
                symbol = "NINE"
            elif rank == "T":
                symbol = "TEN"
            elif rank == "J":
                symbol = "JACK"
            elif rank == "K":
                symbol = "KING"
            elif rank == "Q":
                symbol = "QUEEN"
            elif rank == "A":
                symbol = "ACE"

            returnedCards.append({"symbol": symbol, "suit":card["suit"]})
    return returnedCards

# Takes UPPER Symbol in words (NINE, ACE, JACK)
def calculateCardOutput(cards):
    cardScore = 0
    aces_in_cards = 0
    for card in cards:
        cardSymbol = card["symbol"]
        if cardSymbol == "ACE":
            aces_in_cards = aces_in_cards + 1

        cardScore = cardScore + parseCardtoScore(cardSymbol)

    print(f"Calculating Card Output for cards: {cards}, with an initial card score of {cardScore} and {aces_in_cards} aces")

    cardOutput = ""
    if len(cards) == 2:
        if cards[0]["symbol"] == "ACE" or cards[1]["symbol"] == "ACE":
            cardOutput = f"A{cardScore}"
        elif cards[0]["symbol"] == cards[1]["symbol"]:
            commonSymbol = parseCardtoScore(cards[0]["symbol"])
            cardOutput = f"{commonSymbol}{commonSymbol}"
        else:
            cardOutput = f"{cardScore}"
    elif aces_in_cards > 0:
        if len(cards) == 1:
            cardOutput = "A"
        else:
            if cardScore + aces_in_cards + 10 <= 21:
                cardOutput = f"{cardScore + aces_in_cards + 10}"
            else:
                cardOutput = f"{cardScore + aces_in_cards}"
    else:
        cardOutput = f"{cardScore}"

    return cardOutput

print(f"OBSERVE SCRIPT VERSION {VERSION} {'WITH' if ALLOW_BROWSER_REFRESHING else 'WITHOUT' } BROWSER REFRESHING STARTING!")

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_until_complete(main())