"""Pure game rules. Only views persist state; clients never supply hands or scores."""
import secrets

SUITS = 'SHDC'


def public_card(card):
    return card[:-1] + {'S': '♠', 'H': '♥', 'D': '♦', 'C': '♣'}[card[-1]]


def score(hand):
    return max(sum(11 if c[:-1] == 'A' else 10 if c[:-1] in ('J', 'Q', 'K') else int(c[:-1]) for c in hand if c[-1] == suit) for suit in SUITS)


def active(g):
    return [p for p in g['players'] if p['lives'] > 0]


def next_player(g, current):
    players = active(g)
    return players[(next(i for i, p in enumerate(players) if p['id'] == current) + 1) % len(players)]['id']


def deal(g):
    deck = [rank + suit for suit in SUITS for rank in ['A', *map(str, range(2, 11)), 'J', 'Q', 'K']]
    secrets.SystemRandom().shuffle(deck)
    g.update(phase='playing', deck=deck, discard=[], drawn=False, knocked=None, remaining=[], result=[], round=g.get('round', 0) + 1)
    for p in g['players']:
        p['hand'] = [deck.pop() for _ in range(3)] if p['lives'] else []
    g['discard'].append(deck.pop())
    players = active(g)
    g['turn'] = players[(g['round'] - 1) % len(players)]['id']
    g['message'] = 'A new round. Make yourself at home.'
    g['last_move'] = f"Round {g['round']} was dealt."
    if any(score(p['hand']) == 31 for p in players):
        finish(g, True)


def finish(g, blitz=False):
    players = active(g)
    low = min(score(p['hand']) for p in players)
    losers = [p for p in players if score(p['hand']) < 31] if blitz else [p for p in players if score(p['hand']) == low]
    g['result'] = [{'name': p['name'], 'hand': p['hand'][:], 'score': score(p['hand']), 'lost': p in losers} for p in players]
    for p in losers:
        p['lives'] -= 1
    g['phase'] = 'finished' if len(active(g)) <= 1 else 'round_over'
    g['message'] = ('31! Everyone else loses a life.' if blitz else 'Lowest score loses a life. Ties share the loss.')
    if g['phase'] == 'finished':
        g['message'] += ' ' + (active(g)[0]['name'] + ' wins the game!' if active(g) else 'A shared finish!')


def play(g, pid, verb, index=None):
    if verb in ('start', 'next', 'rematch'):
        if pid != g['players'][0]['id']:
            raise ValueError('Only the host can deal.')
        expected = {'start': 'lobby', 'next': 'round_over', 'rematch': 'finished'}[verb]
        if g['phase'] != expected or len(g['players']) < 2:
            raise ValueError('You need at least two players and a table ready to deal.')
        if verb == 'rematch':
            for p in g['players']:
                p['lives'] = 3
            g['round'] = 0
        deal(g)
        return
    if g['phase'] != 'playing' or g['turn'] != pid:
        raise ValueError('Please wait for your turn.')
    p = next(p for p in g['players'] if p['id'] == pid)
    if verb in ('deck', 'pile'):
        if g['drawn']:
            raise ValueError('Choose a card to discard first.')
        if verb == 'deck' and not g['deck']:
            top = g['discard'].pop()
            g['deck'] = g['discard']
            secrets.SystemRandom().shuffle(g['deck'])
            g['discard'] = [top]
        source = g['deck'] if verb == 'deck' else g['discard']
        if not source:
            raise ValueError('That pile is empty. Draw from the other pile.')
        picked = source.pop()
        p['hand'].append(picked)
        g['turn_draw'] = (p['name'] + ' drew a card from the deck' if verb == 'deck'
                          else p['name'] + ' picked up ' + public_card(picked) + ' from the discard pile')
        g['last_move'] = g['turn_draw'] + '.'
        g['drawn'] = True
        return
    if verb == 'discard':
        if not g['drawn'] or type(index) is not int or not 0 <= index < 4:
            raise ValueError('Draw, then choose a card from your hand.')
        discarded = p['hand'].pop(index)
        g['discard'].append(discarded)
        g['last_move'] = g.get('turn_draw', p['name'] + ' drew a card') + ' and discarded ' + public_card(discarded) + '.'
        g['drawn'] = False
        if score(p['hand']) == 31:
            finish(g, True)
            return
        if g['knocked']:
            g['remaining'].remove(pid)
            if not g['remaining']:
                finish(g)
                return
    elif verb == 'knock':
        if g['drawn'] or g['knocked']:
            raise ValueError('Knock at the start of your turn, before anyone else knocks.')
        g['knocked'] = pid
        g['remaining'] = [x['id'] for x in active(g) if x['id'] != pid]
        g['message'] = p['name'] + ' knocked. Everyone else gets one final turn.'
        g['last_move'] = g['message']
    else:
        raise ValueError('Unknown action.')
    g['turn'] = next_player(g, pid)
