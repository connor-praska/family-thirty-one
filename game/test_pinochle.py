import copy
from django.test import TestCase, Client
from . import pinochle as pin
from .models import Room


def game(**rules):
    return {'game': 'pinochle', 'phase': 'lobby', 'round': 0, 'scores': [0, 0],
            'rules': dict(pin.DEFAULTS, **rules), 'message': 'Welcome',
            'players': [{'id': str(i), 'name': f'Player {i}', 'hand': []} for i in range(4)]}


def cards(*faces):
    return [f'{f}:{i}' for i, f in enumerate(faces)]


class PinochleRulesTests(TestCase):
    def test_deck_and_forced_dealer_bid(self):
        g = game()
        pin.play(g, '0', 'start', {})
        all_cards = [c for p in g['players'] for c in p['hand']]
        self.assertEqual(len(all_cards), 80)
        self.assertEqual(len(set(all_cards)), 80)
        self.assertTrue(all(len(p['hand']) == 20 for p in g['players']))
        for pid in ['1', '2', '3']:
            pin.play(g, pid, 'pass', {})
        self.assertEqual((g['phase'], g['bid'], g['bidder'], g['turn']), ('trump', 50, '0', '0'))

    def test_bid_validation_and_pass_is_final(self):
        g = game()
        pin.deal(g)
        for value in [True, 49, 61, 10001, '50']:
            with self.assertRaises(ValueError):
                pin.play(g, '1', 'bid', {'bid': value})
        pin.play(g, '1', 'bid', {'bid': 50})
        pin.play(g, '2', 'pass', {})
        pin.play(g, '3', 'bid', {'bid': 55})
        pin.play(g, '0', 'pass', {})
        pin.play(g, '1', 'bid', {'bid': 60})
        self.assertEqual(g['turn'], '3')
        with self.assertRaises(ValueError):
            pin.play(g, '2', 'bid', {'bid': 65})

    def test_meld_overlap_and_multiples(self):
        # Example with a run, extra trump marriage, double queens around and pinochle.
        hand = cards('AH', '10H', 'KH', 'KH', 'KH', 'QH', 'QH', 'JH',
                     'QD', 'QD', 'JD', 'QC', 'QC', 'AS', 'KS', 'KS', 'QS', 'QS', 'JS', 'JS')
        self.assertEqual(pin.meld(hand, 'H')['points'], 87)
        double_run = cards(*[r + 'S' for r in pin.RANKS for _ in range(2)])
        self.assertEqual(pin.meld(double_run, 'S')['points'], 150)
        double_pin = cards('QS', 'QS', 'JD', 'JD')
        self.assertEqual(pin.meld(double_pin, 'C')['points'], 30)
        self.assertEqual(pin.meld(cards('10S', '10H', '10D', '10C'), 'H')['points'], 0)

    def test_follow_trump_overtrump_and_equal_card_priority(self):
        g = game()
        pin.deal(g)
        g.update(phase='playing', trump='H', trick=[{'seat': 1, 'card': 'KS:0'}], turn='2')
        g['players'][2]['hand'] = cards('JS', 'AS', 'AH')
        self.assertEqual(list(map(pin.face, pin.legal_cards(g, 2))), ['AS'])
        g['trick'].append({'seat': 3, 'card': 'JH:0'})
        self.assertEqual(set(map(pin.face, pin.legal_cards(g, 2))), {'JS', 'AS'})
        g['players'][2]['hand'] = cards('JH', 'KH', 'AC')
        self.assertEqual(list(map(pin.face, pin.legal_cards(g, 2))), ['KH'])
        g['players'][2]['hand'] = cards('JH', 'AC')
        self.assertEqual(list(map(pin.face, pin.legal_cards(g, 2))), ['JH'])
        self.assertEqual(pin.winner([{'seat': 1, 'card': 'AH:0'}, {'seat': 2, 'card': 'AH:1'}], 'H'), 1)

    def test_private_simultaneous_exchange(self):
        g = game(pass_count=3, marriage_required=False)
        pin.deal(g)
        g.update(phase='trump', turn='1', bidder='1', bid=50)
        pin.play(g, '1', 'trump', {'suit': 'S'})
        before = copy.deepcopy(g)
        first, second = g['players'][1]['hand'][:3], g['players'][3]['hand'][:3]
        pin.play(g, '1', 'exchange', {'cards': first})
        self.assertEqual(g['players'][1]['hand'], before['players'][1]['hand'])
        public = pin.public_state(g, '3')
        self.assertNotIn('pending_pass', public)
        self.assertEqual(public['players'][1]['hand'], [])
        with self.assertRaises(ValueError):
            pin.play(g, '0', 'exchange', {'cards': first})
        with self.assertRaises(ValueError):
            pin.play(g, '3', 'exchange', {'cards': [second[0]] * 3})
        pin.play(g, '3', 'exchange', {'cards': second})
        self.assertEqual(g['phase'], 'melding')
        self.assertTrue(all(c in g['players'][3]['hand'] for c in first))
        self.assertTrue(all(c in g['players'][1]['hand'] for c in second))
        self.assertTrue(all(len(p['hand']) == 20 for p in g['players']))
        self.assertEqual(len(set(c for p in g['players'] for c in p['hand'])), 80)

    def test_scoring_set_and_target_tiebreak(self):
        g = game(target=500)
        pin.deal(g)
        g.update(bidder='0', bid=50, melds=[{'points': 10}] * 4, scores=[490, 490],
                 trick_points=[25, 25], tricks_won=[10, 10])
        pin.finish(g)
        self.assertEqual(g['result']['delta'], [-50, 45])
        self.assertEqual(g['winner'], 1)
        g.update(phase='playing', bid=40, scores=[490, 490])
        pin.finish(g)
        self.assertEqual(g['winner'], 0)
        g['rules']['minimum_tricks'] = 20
        g.update(scores=[0, 0], bid=40, trick_points=[19, 31])
        pin.finish(g)
        self.assertEqual(g['result']['delta'], [-40, 51])

    def test_no_marriage_and_minimum_meld_forfeit(self):
        g = game()
        pin.deal(g)
        g.update(phase='trump', turn='1', bidder='1', bid=50)
        g['players'][1]['hand'] = cards(*(['AS'] * 20))
        with self.assertRaises(ValueError):
            pin.play(g, '1', 'trump', {'suit': 'S'})
        pin.play(g, '1', 'concede', {})
        self.assertEqual(g['scores'], [0, -50])
        g = game(minimum_meld=20)
        pin.deal(g)
        g.update(phase='trump', turn='1', bidder='1', bid=50)
        for p in g['players']:
            p['hand'] = cards('KS', 'QS')
        pin.play(g, '1', 'trump', {'suit': 'S'})
        self.assertEqual(g['phase'], 'round_over')
        self.assertEqual(g['scores'], [0, -50])

    def test_complete_hands_conserve_50_points_and_ready_barrier(self):
        for exchange in [0, 3, 4]:
            for _ in range(5):
                g = game(pass_count=exchange, marriage_required=False, must_beat=bool(_ % 2))
                pin.deal(g)
                pin.play(g, '1', 'bid', {'bid': 50})
                for pid in ['2', '3', '0']:
                    pin.play(g, pid, 'pass', {})
                pin.play(g, '1', 'trump', {'suit': 'H'})
                if exchange:
                    for pid in ['1', '3']:
                        pin.play(g, pid, 'exchange', {'cards': g['players'][int(pid)]['hand'][:exchange]})
                while g['phase'] not in ('round_over', 'finished'):
                    if g['phase'] in ('melding', 'trick_review'):
                        for pid in ['0', '1', '2']:
                            pin.play(g, pid, 'ready', {})
                        self.assertNotEqual(g['phase'], 'playing')
                        with self.assertRaises(ValueError):
                            pin.play(g, '0', 'ready', {})
                        pin.play(g, '3', 'ready', {})
                    else:
                        i = pin.seat(g, g['turn'])
                        pin.play(g, g['turn'], 'card', {'card': pin.legal_cards(g, i)[0]})
                self.assertEqual(sum(g['trick_points']), 50)
                self.assertEqual(sum(g['tricks_won']), 20)
                self.assertTrue(all(not p['hand'] for p in g['players']))
                g['phase'] = 'round_over'
                pin.play(g, '0', 'next', {})
                self.assertEqual(g['dealer'], 1)
                g['phase'] = 'finished'
                pin.play(g, '0', 'rematch', {})
                self.assertEqual(g['scores'], [0, 0])
                self.assertEqual(g['round'], 1)


class PinochleRoomTests(TestCase):
    def test_complete_hand_through_four_independent_sessions(self):
        clients = [Client() for _ in range(4)]
        clients[0].post('/games/pinochle/create/', {'name': 'Host', 'marriage_required': 'no'})
        room = Room.objects.get()
        base = f'/room/{room.code}/'
        for i in range(1, 4):
            clients[i].post('/join/', {'name': f'Player {i}', 'code': room.code})

        def action(index, verb, **extra):
            state = clients[index].get(base + 'state/').json()
            response = clients[index].post(base + 'action/', dict(version=state['version'], action=verb, **extra), content_type='application/json')
            self.assertEqual(response.status_code, 200, response.content)

        action(0, 'start')
        for _ in range(250):
            state = clients[0].get(base + 'state/').json()
            phase = state['phase']
            if phase in ('round_over', 'finished'):
                break
            if phase in ('melding', 'trick_review'):
                for i in range(4):
                    action(i, 'ready')
            else:
                current = next(p['seat'] for p in state['players'] if p['turn'])
                own = clients[current].get(base + 'state/').json()
                if phase == 'bidding':
                    action(current, 'bid', bid=50) if not state['bid'] else action(current, 'pass')
                elif phase == 'trump':
                    action(current, 'trump', suit='H')
                else:
                    self.assertEqual(phase, 'playing')
                    action(current, 'card', card=own['legal'][0])
        else:
            self.fail('A complete hand did not finish.')
        self.assertEqual(sum(state['result']['trick_points']), 50)
        self.assertEqual(len(state['history']), 1)
        action(0, 'next')
        self.assertEqual(clients[0].get(base + 'state/').json()['round'], 2)

    def test_room_lifecycle_privacy_and_shared_chat(self):
        clients = [Client() for _ in range(5)]
        response = clients[0].post('/games/pinochle/create/', {'name': 'Host', 'target': 250})
        self.assertEqual(response.status_code, 302)
        room = Room.objects.get()
        base = f'/room/{room.code}/'
        self.assertTemplateUsed(clients[1].get(base), 'pinochle.html')
        for i in range(1, 4):
            self.assertEqual(clients[i].post('/join/', {'name': f'Guest {i}', 'code': room.code}).status_code, 302)
        self.assertEqual(clients[4].post('/join/', {'name': 'Extra', 'code': room.code}).status_code, 400)
        self.assertTemplateUsed(clients[0].get(base), 'pinochle_room.html')
        s = clients[0].get(base + 'state/').json()
        self.assertEqual(s['rules']['target'], 250)
        self.assertEqual([p['team'] for p in s['players']], [0, 1, 0, 1])
        self.assertEqual(clients[1].post(base + 'action/', {'version': s['version'], 'action': 'start'}, content_type='application/json').status_code, 400)
        self.assertEqual(clients[0].post(base + 'action/', {'version': s['version'], 'action': 'start'}, content_type='application/json').status_code, 200)
        s = clients[2].get(base + 'state/').json()
        self.assertEqual([len(p['hand']) for p in s['players']], [0, 0, 20, 0])
        self.assertNotIn('pending_pass', s)
        self.assertNotIn('bidder', [p for p in s['players'] if p['you']][0])
        self.assertEqual(clients[2].post(base + 'chat/', {'text': 'Go team!'}, content_type='application/json').status_code, 200)
        self.assertEqual(clients[0].get(base + 'state/').json()['messages'][-1]['text'], 'Go team!')
        self.assertEqual(clients[4].get(base + 'state/').status_code, 403)
        self.assertContains(clients[0].get('/'), '/games/pinochle/')

    def test_rules_are_validated_and_start_requires_four(self):
        browser = Client()
        self.assertEqual(browser.post('/games/pinochle/create/', {'name': 'Host', 'pass_count': 100}).status_code, 400)
        self.assertFalse(Room.objects.exists())
        browser.post('/games/pinochle/create/', {'name': 'Host'})
        room = Room.objects.get()
        self.assertEqual(browser.post(f'/room/{room.code}/action/', {'version': 0, 'action': 'start'}, content_type='application/json').status_code, 400)
