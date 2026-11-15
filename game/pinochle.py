"""Four-player, double-deck partnership pinochle. All decisions validated here."""
from collections import Counter
import secrets

SUITS = 'SHDC'
RANKS = ['J', 'Q', 'K', '10', 'A']
DEFAULTS = {'target': 500, 'opening_bid': 50, 'minimum_meld': 0, 'minimum_tricks': 0,
            'pass_count': 0, 'marriage_required': True, 'bid_fives': True, 'must_beat': True}


def rules(values):
    result = DEFAULTS.copy()
    for key, allowed in {'target': (250, 500, 1000), 'opening_bid': (25, 50),
                         'minimum_meld': (0, 20), 'minimum_tricks': (0, 20), 'pass_count': (0, 3, 4)}.items():
        try:
            result[key] = int(values.get(key, result[key]))
        except (TypeError, ValueError):
            raise ValueError('Invalid house rules.')
        if result[key] not in allowed:
            raise ValueError('Invalid house rules.')
    for key in ('marriage_required', 'bid_fives', 'must_beat'):
        value = values.get(key, 'yes')
        if value not in ('yes', 'no'):
            raise ValueError('Invalid house rules.')
        result[key] = value == 'yes'
    return result


def face(card):
    return card.split(':')[0]


def suit(card):
    return face(card)[-1]


def rank(card):
    return RANKS.index(face(card)[:-1])


def label(card):
    return face(card)[:-1] + dict(zip(SUITS, '♠♥♦♣'))[suit(card)]


def meld(hand, trump):
    counts = Counter(map(face, hand))
    used = Counter()
    details = []

    def add(title, faces, count, points):
        if count:
            details.append({'name': title, 'count': count, 'points': points})
            for f in faces:
                used[f] = max(used[f], count)

    run = [r + trump for r in RANKS]
    n = min(counts[f] for f in run)
    add('Trump run', run, n, [0, 15, 150, 225, 300][n])
    for s in SUITS:
        pair = ['K' + s, 'Q' + s]
        pairs = min(counts[f] for f in pair)
        extra = pairs - n if s == trump else pairs
        # Runs already include their marriage; show only additional pairs.
        if extra:
            details.append({'name': 'Trump marriage' if s == trump else s + ' marriage', 'count': extra, 'points': extra * (4 if s == trump else 2)})
            for f in pair:
                used[f] = max(used[f], pairs)
    pin = ['QS', 'JD']
    n = min(counts[f] for f in pin)
    add('Pinochle', pin, n, [0, 4, 30, 60, 90][n])
    for r, single in [('A', 10), ('K', 8), ('Q', 6), ('J', 4)]:
        faces = [r + s for s in SUITS]
        n = min(counts[f] for f in faces)
        add(r + ' around', faces, n, [0, single, single * 10, single * 15, single * 20][n])
    shown = []
    for c in hand:
        if used[face(c)] > 0:
            shown.append(c)
            used[face(c)] -= 1
    return {'points': sum(d['points'] for d in details), 'details': details, 'cards': shown}


def seat(g, pid):
    return next(i for i, p in enumerate(g['players']) if p['id'] == pid)


def turn(g, index):
    g['turn'] = g['players'][index % 4]['id']


def deal(g):
    deck = [r + s + ':' + str(copy) for s in SUITS for r in RANKS for copy in range(4)]
    secrets.SystemRandom().shuffle(deck)
    g.update(phase='bidding', round=g.get('round', 0) + 1, bid=0, bidder=None, passed=[], trump=None,
             melds=[], trick=[], last_trick=[], trick_points=[0, 0], tricks_won=[0, 0], ready=[],
             pending_pass={}, history=g.get('history', []), result=None)
    g['dealer'] = (g['round'] - 1) % 4
    for i, p in enumerate(g['players']):
        p['hand'] = sorted(deck[i * 20:(i + 1) * 20], key=lambda c: (SUITS.index(suit(c)), -rank(c), c))
    turn(g, g['dealer'] + 1)
    g['message'] = f"Hand {g['round']}: bidding starts to the dealer’s left."
    g['last_move'] = g['message']


def beats(card, previous, lead, trump):
    if suit(card) == suit(previous):
        return rank(card) > rank(previous)
    return suit(card) == trump or (suit(card) == lead and suit(previous) != trump)


def winner(trick, trump):
    best = trick[0]
    for entry in trick[1:]:
        if beats(entry['card'], best['card'], suit(trick[0]['card']), trump):
            best = entry
    return best['seat']


def legal_cards(g, index):
    hand = g['players'][index]['hand']
    if g['phase'] != 'playing' or g['turn'] != g['players'][index]['id']:
        return []
    if not g['trick']:
        return hand[:]
    lead = suit(g['trick'][0]['card'])
    choices = [c for c in hand if suit(c) == lead] or [c for c in hand if suit(c) == g['trump']] or hand[:]
    if g['rules']['must_beat']:
        best = next(e['card'] for e in g['trick'] if e['seat'] == winner(g['trick'], g['trump']))
        choices = [c for c in choices if beats(c, best, lead, g['trump'])] or choices
    return choices


def finish(g, forfeit=False, no_marriage=False):
    team = seat(g, g['bidder']) % 2
    other = 1 - team
    meld_points = [sum(g['melds'][i]['points'] for i in range(4) if i % 2 == t) if g['melds'] else 0 for t in (0, 1)]
    credited = [m if m >= g['rules']['minimum_meld'] else 0 for m in meld_points]
    earned = [credited[t] + g['trick_points'][t] if g['trick_points'][t] >= g['rules']['minimum_tricks'] and g['tricks_won'][t] else 0 for t in (0, 1)]
    made = not forfeit and meld_points[team] >= g['rules']['minimum_meld'] and earned[team] >= g['bid']
    delta = earned[:]
    delta[team] = earned[team] if made else -g['bid']
    if forfeit:
        delta[other] = 0 if no_marriage else credited[other]
    g['scores'] = [g['scores'][t] + delta[t] for t in (0, 1)]
    g['result'] = {'bid_team': team, 'bid': g['bid'], 'made': made, 'meld': meld_points,
                   'trick_points': g['trick_points'][:], 'delta': delta, 'scores': g['scores'][:]}
    g['history'] = (g['history'] + [dict(g['result'], round=g['round'])])[-20:]
    winners = [t for t in (0, 1) if g['scores'][t] >= g['rules']['target']]
    winning = team if team in winners else (winners[0] if winners else None)
    g['winner'] = winning
    g['phase'] = 'finished' if winning is not None else 'round_over'
    g['message'] = f"Team {team + 1} {'made' if made else 'was set on'} the {g['bid']} bid."
    if winning is not None:
        g['message'] += f' Team {winning + 1} wins!'


def reveal(g):
    g['melds'] = [meld(p['hand'], g['trump']) for p in g['players']]
    team = seat(g, g['bidder']) % 2
    if sum(g['melds'][i]['points'] for i in range(4) if i % 2 == team) < g['rules']['minimum_meld']:
        finish(g, forfeit=True)
    else:
        g['phase'] = 'melding'
        g['ready'] = []
        g['message'] = 'Meld is on the table. Everyone confirms before trick play.'


def play(g, pid, verb, body):
    i = seat(g, pid)
    p = g['players'][i]
    phase = g['phase']
    if verb in ('start', 'next', 'rematch'):
        expected = {'start': 'lobby', 'next': 'round_over', 'rematch': 'finished'}[verb]
        if i != 0 or phase != expected or len(g['players']) != 4:
            raise ValueError('The host can deal when four players are seated and the table is ready.')
        if verb == 'rematch':
            g.update(scores=[0, 0], round=0, history=[])
        deal(g)
        return
    if verb == 'ready' and phase in ('melding', 'trick_review'):
        if pid in g['ready']:
            raise ValueError('You are already ready.')
        g['ready'].append(pid)
        g['last_move'] = p['name'] + ' is ready.'
        if len(g['ready']) == 4:
            g['phase'] = 'playing'
            g['ready'] = []
            g['trick'] = []
            g['message'] = 'Follow suit, trump when void, and beat the winning card when required.'
        return
    if verb == 'exchange' and phase == 'passing':
        if i % 2 != seat(g, g['bidder']) % 2 or pid in g['pending_pass']:
            raise ValueError('Wait for the bidding partners to exchange.')
        selected = body.get('cards')
        if not isinstance(selected, list) or len(selected) != g['rules']['pass_count'] or any(not isinstance(c, str) for c in selected) or len(set(selected)) != len(selected) or not all(c in p['hand'] for c in selected):
            raise ValueError('Select the required number of cards from your hand.')
        g['pending_pass'][pid] = selected
        g['last_move'] = p['name'] + ' selected cards for the private exchange.'
        if len(g['pending_pass']) == 2:
            for sender, cards in g['pending_pass'].items():
                source = seat(g, sender)
                for c in cards:
                    g['players'][source]['hand'].remove(c)
                g['players'][(source + 2) % 4]['hand'].extend(cards)
            g['pending_pass'] = {}
            reveal(g)
        return
    if phase not in ('bidding', 'trump', 'playing') or g['turn'] != pid:
        raise ValueError('Please wait for your turn.')
    if phase == 'bidding' and verb in ('bid', 'pass'):
        if verb == 'bid':
            value = body.get('bid')
            if type(value) is not int or value < max(g['rules']['opening_bid'], g['bid'] + 1) or value > 10000 or (g['rules']['bid_fives'] and value > 60 and value % 5):
                raise ValueError('Bid above the current bid; above 60, use multiples of five if enabled.')
            g.update(bid=value, bidder=pid)
            g['last_move'] = p['name'] + f' bid {value}.'
        else:
            g['passed'].append(pid)
            g['last_move'] = p['name'] + ' passed.'
        remaining = [n for n in range(4) if g['players'][n]['id'] not in g['passed']]
        if len(remaining) == 1:
            g['bidder'] = g['players'][remaining[0]]['id']
            g['bid'] = g['bid'] or g['rules']['opening_bid']
            g['phase'] = 'trump'
            turn(g, remaining[0])
            g['message'] = g['players'][remaining[0]]['name'] + f" won the bid at {g['bid']}. Choose trump."
        else:
            n = (i + 1) % 4
            while n not in remaining:
                n = (n + 1) % 4
            turn(g, n)
        return
    if phase == 'trump' and verb == 'trump':
        trump = body.get('suit')
        if trump not in tuple(SUITS):
            raise ValueError('Choose a trump suit.')
        if g['rules']['marriage_required'] and not all(r + trump in list(map(face, p['hand'])) for r in ('K', 'Q')):
            raise ValueError('Choose a suit with a king and queen, or concede if none exists.')
        g['trump'] = trump
        g['last_move'] = p['name'] + ' chose ' + dict(zip(SUITS, '♠♥♦♣'))[trump] + ' as trump.'
        if g['rules']['pass_count']:
            g['phase'] = 'passing'
            g['message'] = 'Bidding partners select cards simultaneously. Selections stay private until both submit.'
        else:
            reveal(g)
        return
    if phase == 'trump' and verb == 'concede':
        if not g['rules']['marriage_required'] or any(all(r + s in list(map(face, p['hand'])) for r in ('K', 'Q')) for s in SUITS):
            raise ValueError('Choose a trump suit; you have a valid marriage.')
        g['last_move'] = p['name'] + ' had no marriage and conceded the bid.'
        finish(g, forfeit=True, no_marriage=True)
        return
    if phase == 'playing' and verb == 'card':
        c = body.get('card')
        if c not in legal_cards(g, i):
            raise ValueError('Choose a highlighted legal card. Follow suit, trump when void, and beat when possible.')
        p['hand'].remove(c)
        g['trick'].append({'seat': i, 'card': c})
        g['last_move'] = p['name'] + ' played ' + label(c) + '.'
        if len(g['trick']) < 4:
            turn(g, i + 1)
        else:
            won = winner(g['trick'], g['trump'])
            points = sum(face(e['card'])[:-1] in ('A', '10', 'K') for e in g['trick'])
            last = not any(p['hand'] for p in g['players'])
            points += 2 if last else 0
            g['trick_points'][won % 2] += points
            g['tricks_won'][won % 2] += 1
            g['last_trick'] = g['trick'][:]
            g['last_move'] += ' ' + g['players'][won]['name'] + f' won the trick ({points} points).'
            turn(g, won)
            if last:
                finish(g)
            else:
                g['phase'] = 'trick_review'
                g['ready'] = []
                g['message'] = 'Review the trick, then everyone taps Ready. The winner leads next.'
        return
    raise ValueError('That action is not available now.')


def public_state(g, pid):
    i = seat(g, pid)
    players = [{'name': p['name'], 'seat': n, 'team': n % 2, 'you': n == i, 'host': n == 0,
                'turn': p['id'] == g.get('turn'), 'hand': p['hand'] if n == i else [],
                'count': len(p['hand']), 'passed': p['id'] in g.get('passed', []),
                'ready': p['id'] in g.get('ready', [])} for n, p in enumerate(g['players'])]
    keys = ('phase', 'round', 'rules', 'scores', 'bid', 'trump', 'melds', 'trick', 'last_trick',
            'trick_points', 'tricks_won', 'message', 'last_move', 'result', 'history', 'dealer', 'winner')
    data = {k: g.get(k) for k in keys}
    data.update(game='pinochle', players=players, your_turn=g.get('turn') == pid,
                bidder=seat(g, g['bidder']) if g.get('bidder') else None,
                legal=legal_cards(g, i), exchange_submitted=pid in g.get('pending_pass', {}))
    return data
