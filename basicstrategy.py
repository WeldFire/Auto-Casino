import pandas

STRATEGY_LEGEND = {
    "P" : "SPLIT",
    "S" : "STAND",
    "H" : "HIT",
    "D" : "DOUBLE DOWN",
    "Sr": "Not sure"
}

df = pandas.read_csv('basicstrategy_hit_soft17.csv')

def calculate_basic_strategy(player_cards, dealer_card):
    player_moves = df[df['Player'] == f'{player_cards}']
    print(f"Basic Strategy - Players Hand - {player_cards}")
    dealer_moves = player_moves[f'{dealer_card}'].values[0]
    print(f"Basic Strategy - Dealer's Hand - {dealer_card}")
    action = STRATEGY_LEGEND[dealer_moves]
    print(f"Basic Strategy - You should - {action}")
    return action


if __name__ == '__main__':
    calculate_basic_strategy("22", "4")