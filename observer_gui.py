# Import Module
from tkinter import *
from tkinter import ttk
import asyncio

LOOP_ACTIVE = True

# create root window
root = Tk()
root.attributes('-topmost', 'true')

# Combobox creation 
casinoSelectedFunction = None
casinoCombo = ttk.Combobox(root, values=["Chumba", "Modo"])
casinoCombo.grid(column=0, row=1)

async def casinoOption_selected(event):
    selected_option = casinoCombo.get()
    if(casinoSelectedFunction is not None):
        print("Calling registered function with:", selected_option)
        await casinoSelectedFunction(selected_option)
    else:
        print("You selected:", selected_option, "but there was no registered function so nothing else was triggered")

def casinoOption_registerFunction(callbackFunction):
    global casinoSelectedFunction
    casinoSelectedFunction = callbackFunction
    print("New callback function registered")

# casinoCombo.bind("<<ComboboxSelected>>", casinoOption_selected)
casinoCombo.bind("<<ComboboxSelected>>", lambda event: asyncio.ensure_future(casinoOption_selected(event)))

# adding a label to the root window
lblStatus = Label(root, text = "Status: Select a casino in the dropdown to get started")
lblDealer = Label(root, text = "Dealer Hand: Unknown")
lblPlayer = Label(root, text = "Player Hand: Unknown")
lblAction = Label(root, text = "Action: Unknown")
lblStatus.grid(column=0, row=0)
lblDealer.grid(column=0, row=2)
lblPlayer.grid(column=0, row=3)
lblAction.grid(column=0, row=5)


def calculateNewLabel(oldText, newText):
    splitterIndex = oldText.find(':')
    if splitterIndex > 0:
        return oldText[0:splitterIndex+2] + newText
    return oldText + " " + newText

def updateStatus(newStatus):
    lblStatus.configure(text=calculateNewLabel(lblStatus["text"], newStatus))

def updateDealerCards(newStatus):
    lblDealer.configure(text=calculateNewLabel(lblDealer["text"], newStatus))

def updatePlayerCards(newStatus):
    lblPlayer.configure(text=calculateNewLabel(lblPlayer["text"], newStatus))

def updateAction(newStatus):
    lblAction.configure(text=calculateNewLabel(lblAction["text"], newStatus))

def getSelectedOption():
    return casinoCombo.get()

async def start_gui():
    # root window title and dimension
    root.title("Casino Observer GUI")
    # root.geometry('350x200')

    # Execute Tkinter
    # root.mainloop()
    while LOOP_ACTIVE:
        await asyncio.sleep(0.1)
        root.update()

if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_gui())
