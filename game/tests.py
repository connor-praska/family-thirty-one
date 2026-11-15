from django.test import TestCase, Client, override_settings
from .engine import score, play, deal
from .models import Room, RoomMessage


class RulesTests(TestCase):
    def game(self):
        return {'phase': 'lobby', 'round': 0, 'players': [{'id': str(i), 'name': str(i), 'lives': 3, 'hand': []} for i in range(3)]}

    def test_score_uses_one_suit(self):
        self.assertEqual(score(['AH', 'KH', 'QH']), 31)
        self.assertEqual(score(['AS', 'KH', 'QH']), 20)
        self.assertEqual(score(['7S', '7H', '7D']), 7)

    def test_knock_gives_each_other_player_exactly_one_turn(self):
        g = self.game()
        deal(g)
        g.update(phase='playing', turn='0', knocked=None)
        for p in g['players']:
            p['hand'] = ['2S', '3H', '4D']
        play(g, '0', 'knock')
        self.assertEqual(g['turn'], '1')
        for pid in ['1', '2']:
            play(g, pid, 'deck')
            play(g, pid, 'discard', 3)
        self.assertEqual(g['phase'], 'round_over')
        self.assertEqual([p['lives'] for p in g['players']], [2, 2, 2])

    def test_turns_and_draw_order(self):
        g = self.game()
        deal(g)
        g['phase'] = 'playing'
        pid = g['turn']
        with self.assertRaises(ValueError):
            play(g, str((int(pid) + 1) % 3), 'deck')
        with self.assertRaises(ValueError):
            play(g, pid, 'discard', 0)
        play(g, pid, 'deck')
        with self.assertRaises(ValueError):
            play(g, pid, 'deck')
        with self.assertRaises(ValueError):
            play(g, pid, 'knock')

    def test_31_and_elimination(self):
        g = self.game()
        deal(g)
        g.update(phase='playing', turn='0', drawn=True)
        g['players'][0]['hand'] = ['AH', 'KH', 'QH', '2S']
        for p in g['players'][1:]:
            p.update(hand=['2H', '3D', '4C'], lives=1)
        play(g, '0', 'discard', 3)
        self.assertEqual(g['phase'], 'finished')
        self.assertEqual([p['lives'] for p in g['players']], [3, 0, 0])

    def test_deal_has_unique_cards(self):
        g = self.game()
        deal(g)
        cards = g['deck'] + g['discard'] + [c for p in g['players'] for c in p['hand']]
        self.assertEqual(len(cards), 52)
        self.assertEqual(len(set(cards)), 52)

    def test_public_moves_and_knock_reset(self):
        g = self.game()
        deal(g)
        g.update(phase='playing', turn='0', deck=['AS'], discard=['7H'])
        g['players'][0]['hand'] = ['2C', '3D', '4H']
        play(g, '0', 'deck')
        self.assertEqual(g['last_move'], '0 drew a card from the deck.')
        self.assertNotIn('A♠', g['last_move'])
        play(g, '0', 'discard', 0)
        self.assertEqual(g['last_move'], '0 drew a card from the deck and discarded 2♣.')
        play(g, '1', 'pile')
        self.assertEqual(g['last_move'], '1 picked up 2♣ from the discard pile.')
        play(g, '1', 'discard', 3)
        play(g, '2', 'knock')
        self.assertIn('2 knocked', g['last_move'])
        self.assertEqual(g['remaining'], ['0', '1'])
        deal(g)
        self.assertIsNone(g['knocked'])
        self.assertEqual(g['last_move'], 'Round 2 was dealt.')


class RoomTests(TestCase):
    def setUp(self):
        self.host, self.guest = Client(), Client()
        self.host.post('/create/', {'name': 'Host'})
        self.room = Room.objects.get()
        self.code = self.room.code
        self.base = f'/room/{self.code}/'
        self.guest.post('/join/', {'name': 'Grandma', 'code': self.code})

    def move(self, client, action, **kwargs):
        version = client.get(self.base + 'state/').json()['version']
        return client.post(self.base + 'action/', {'action': action, 'version': version, **kwargs}, content_type='application/json')

    def test_collection_to_game_and_existing_invites(self):
        home = self.host.get('/')
        self.assertTemplateUsed(home, 'home.html')
        self.assertContains(home, 'href="/games/31/"')
        game = self.host.get('/games/31/')
        self.assertTemplateUsed(game, 'thirtyone.html')
        self.assertContains(game, 'action="/create/"')
        invited = Client().get(self.base)
        self.assertTemplateUsed(invited, 'thirtyone.html')
        self.assertContains(invited, self.code)
        self.assertContains(invited, 'action="/join/"')
        invalid = Client().post('/join/', {'name': 'New player', 'code': 'BADCODE'})
        self.assertTemplateUsed(invalid, 'thirtyone.html')
        self.assertContains(invalid, 'That table was not found.', status_code=400)
        self.assertEqual(self.move(self.host, 'start').status_code, 200)
        self.assertEqual(self.host.get(self.base).status_code, 200)

    def test_private_hands_and_reconnect(self):
        self.assertEqual(self.move(self.host, 'start').status_code, 200)
        s = self.guest.get(self.base + 'state/').json()
        self.assertEqual(len(next(p['hand'] for p in s['players'] if p['you'])), 3)
        self.assertEqual(next(p['hand'] for p in s['players'] if not p['you']), [])
        self.assertNotIn('deck', s)
        self.assertEqual(Client().get(self.base + 'state/').status_code, 403)
        self.assertEqual(self.guest.get(self.base).status_code, 200)

    def test_only_host_can_start_and_stale_requests_fail(self):
        self.assertEqual(self.move(self.guest, 'start').status_code, 400)
        self.assertEqual(self.move(self.host, 'start').status_code, 200)
        response = self.host.post(self.base + 'action/', {'action': 'deck', 'version': -1}, content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_join_restrictions(self):
        third = Client()
        self.assertEqual(third.post('/join/', {'name': 'Grandma', 'code': self.code}).status_code, 400)
        self.move(self.host, 'start')
        self.assertEqual(third.post('/join/', {'name': 'Grandpa', 'code': self.code}).status_code, 400)

    def test_csrf_is_required(self):
        response = Client(enforce_csrf_checks=True).post('/create/', {'name': 'Someone'})
        self.assertEqual(response.status_code, 403)

    def test_chat_membership_validation_and_game_version(self):
        url = self.base + 'chat/'
        self.assertEqual(Client().post(url, {'text': 'Hello'}, content_type='application/json').status_code, 403)
        for text in ['', '   ', 'a' * 301, 123]:
            self.assertEqual(self.host.post(url, {'text': text}, content_type='application/json').status_code, 400)
        before = self.host.get(self.base + 'state/').json()['version']
        self.assertEqual(self.host.post(url, {'text': '<b>Hello!</b>', 'author': 'Server', 'kind': 'event'}, content_type='application/json').status_code, 200)
        state = self.guest.get(self.base + 'state/').json()
        self.assertEqual(state['version'], before)
        message = state['messages'][-1]
        self.assertEqual((message['author'], message['kind'], message['text']), ('Host', 'chat', '<b>Hello!</b>'))
        self.assertNotIn('player_id', message)
        self.assertEqual(self.host.post(url, {'text': 'Again'}, content_type='application/json').status_code, 429)
        self.assertEqual(self.move(self.host, 'start').status_code, 200)

    def test_events_are_public_and_history_is_bounded(self):
        self.move(self.host, 'start')
        r = Room.objects.get(pk=self.room.pk)
        r.data.update(phase='playing', turn=r.data['players'][0]['id'], deck=['AS'], discard=['7H'])
        r.data['players'][0]['hand'] = ['2C', '3D', '4H']
        r.save()
        self.move(self.host, 'deck')
        state = self.guest.get(self.base + 'state/').json()
        self.assertEqual(state['messages'][-1]['text'], 'Host drew a card from the deck.')
        self.assertEqual(state['messages'][-1]['kind'], 'event')
        self.move(self.host, 'discard', index=0)
        self.move(self.guest, 'knock')
        state = self.host.get(self.base + 'state/').json()
        self.assertIn('Grandma knocked', state['knock_notice'])
        self.assertTrue(state['knock_key'])
        RoomMessage.objects.bulk_create([RoomMessage(room=r, author='Host', text='hello') for _ in range(110)])
        self.guest.post(self.base + 'chat/', {'text': 'Next game?'}, content_type='application/json')
        self.assertEqual(r.messages.count(), 100)
        self.assertEqual(len(self.host.get(self.base + 'state/').json()['messages']), 80)

    def test_server_name_is_reserved(self):
        for name in ['Server', ' server ', 'SERVER']:
            self.assertEqual(Client().post('/create/', {'name': name}).status_code, 400)
            self.assertEqual(Client().post('/join/', {'name': name, 'code': self.code}).status_code, 400)

    @override_settings(ALLOWED_HOSTS=['family.onrender.com'], CSRF_TRUSTED_ORIGINS=['https://family.onrender.com'])
    def test_https_origin_through_hosting_proxy(self):
        browser = Client(enforce_csrf_checks=True)
        browser.get('/', HTTP_HOST='family.onrender.com')
        token = browser.cookies['csrftoken'].value
        response = browser.post('/create/', {'name': 'Family', 'csrfmiddlewaretoken': token}, HTTP_HOST='family.onrender.com', HTTP_ORIGIN='https://family.onrender.com')
        self.assertEqual(response.status_code, 302)
        response = browser.post('/create/', {'name': 'Other', 'csrfmiddlewaretoken': token}, HTTP_HOST='family.onrender.com', HTTP_ORIGIN='https://another.onrender.com')
        self.assertEqual(response.status_code, 403)
