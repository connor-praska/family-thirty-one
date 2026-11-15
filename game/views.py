import json
import secrets
import string
from datetime import timedelta
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.utils import timezone
from .models import Room, RoomMessage
from .engine import play, score
from . import pinochle


def home(request):
    return render(request, 'home.html')


def thirtyone(request):
    return render(request, 'thirtyone.html')


def pinochle_home(request):
    return render(request, 'pinochle.html')


def lobby_template(data):
    return 'pinochle.html' if data.get('game') == 'pinochle' else 'thirtyone.html'


def name(request):
    value = request.POST.get('name', '').strip()
    if not 1 <= len(value) <= 24:
        raise ValueError('Enter a name between 1 and 24 characters.')
    if value.casefold() == 'server':
        raise ValueError('Server is reserved for game announcements. Choose another name.')
    return value


def player(request, code):
    return request.session.get('rooms', {}).get(code)


def remember(request, code, pid):
    rooms = request.session.get('rooms', {})
    rooms[code] = pid
    request.session['rooms'] = rooms


@require_POST
def create(request, game_type='31'):
    template = 'pinochle.html' if game_type == 'pinochle' else 'thirtyone.html'
    try:
        n = name(request)
        house_rules = pinochle.rules(request.POST) if game_type == 'pinochle' else None
    except ValueError as e:
        return render(request, template, {'error': str(e)}, status=400)
    code = ''.join(secrets.choice(string.ascii_uppercase.replace('O', '').replace('I', '')) for _ in range(8))
    pid = secrets.token_urlsafe(24)
    data = {'phase': 'lobby', 'round': 0, 'players': [{'id': pid, 'name': n, 'lives': 3, 'hand': []}], 'message': 'The best seat is the one with family.'}
    if house_rules is not None:
        data.update(game='pinochle', rules=house_rules, scores=[0, 0])
    Room.objects.create(code=code, data=data)
    remember(request, code, pid)
    return redirect('/room/' + code + '/')


@require_POST
def join(request):
    code = request.POST.get('code', '').strip().upper()
    existing = Room.objects.filter(code=code).first()
    template = lobby_template(existing.data) if existing else 'thirtyone.html'
    try:
        n = name(request)
        with transaction.atomic():
            r = Room.objects.filter(code=code).first()
            if not r:
                raise ValueError('That table was not found. Check the room code.')
            if player(request, code):
                return redirect('/room/' + code + '/')
            g = r.data
            if g['phase'] != 'lobby' or len(g['players']) >= (4 if g.get('game') == 'pinochle' else 6):
                raise ValueError('This table has started or is full. Ask the host for a new table.')
            if any(p['name'].casefold() == n.casefold() for p in g['players']):
                raise ValueError('That name is taken at this table. Try another name.')
            pid = secrets.token_urlsafe(24)
            g['players'].append({'id': pid, 'name': n, 'lives': 3, 'hand': []})
            if not Room.objects.filter(pk=r.pk, version=r.version).update(data=g, version=r.version + 1):
                raise ValueError('Someone joined at the same moment. Please try again.')
        remember(request, code, pid)
        return redirect('/room/' + code + '/')
    except ValueError as e:
        return render(request, template, {'error': str(e), 'code': code}, status=400)


def room(request, code):
    r = get_object_or_404(Room, code=code)
    if not player(request, code):
        return render(request, lobby_template(r.data), {'code': code})
    return render(request, 'pinochle_room.html' if r.data.get('game') == 'pinochle' else 'room.html', {'code': r.code})


def state(request, code):
    r = get_object_or_404(Room, code=code)
    pid = player(request, code)
    if not pid or not any(p['id'] == pid for p in r.data['players']):
        return JsonResponse({'error': 'Join this table first.'}, status=403)
    g = r.data
    if g.get('game') == 'pinochle':
        payload = pinochle.public_state(g, pid)
        payload['version'] = r.version
    else:
        players = [{'name': p['name'], 'lives': p['lives'], 'you': p['id'] == pid, 'host': i == 0, 'turn': p['id'] == g.get('turn'), 'knocked': p['id'] == g.get('knocked'), 'hand': p['hand'] if p['id'] == pid else []} for i, p in enumerate(g['players'])]
        hand = next(p['hand'] for p in players if p['you'])
        payload = {'version': r.version, 'phase': g['phase'], 'round': g['round'], 'players': players, 'your_turn': g.get('turn') == pid, 'drawn': g.get('drawn', False), 'knocked': bool(g.get('knocked')), 'top': g.get('discard', [None])[-1] if g.get('discard') else None, 'deck_count': len(g.get('deck', [])), 'message': g['message'], 'score': score(hand) if hand else 0, 'result': g.get('result', [])}
        payload['last_move'] = g.get('last_move', '')
        payload['knock_notice'] = (next(p['name'] for p in g['players'] if p['id'] == g['knocked']) + ' knocked. '
                                   + (f"{len(g.get('remaining', []))} final turn(s) remaining." if g['phase'] == 'playing' else 'The round is over.')) if g.get('knocked') else ''
        payload['knock_key'] = f"{g.get('round', 0)}:{g.get('knocked')}" if g.get('knocked') else ''
    payload['messages'] = list(reversed(list(r.messages.order_by('-id').values('id', 'kind', 'author', 'text')[:80])))
    response = JsonResponse(payload)
    response['Cache-Control'] = 'no-store'
    return response


def trim_messages(room):
    cutoff = list(room.messages.order_by('-id').values_list('id', flat=True)[99:100])
    if cutoff:
        room.messages.filter(id__lt=cutoff[0]).delete()


@require_POST
def chat(request, code):
    r = get_object_or_404(Room, code=code)
    pid = player(request, code)
    member = next((p for p in r.data['players'] if p['id'] == pid), None)
    if not member:
        return JsonResponse({'error': 'Join this table first.'}, status=403)
    try:
        body = json.loads(request.body)
        message = body.get('text') if isinstance(body, dict) else None
        if not isinstance(message, str) or not 1 <= len(message.strip()) <= 300:
            raise ValueError('Enter a message between 1 and 300 characters.')
        with transaction.atomic():
            if r.messages.filter(kind='chat', player_id=pid, created_at__gt=timezone.now() - timedelta(seconds=2)).exists():
                return JsonResponse({'error': 'Give everyone a moment—try again in two seconds.'}, status=429)
            RoomMessage.objects.create(room=r, author=member['name'], player_id=pid, text=message.strip())
            trim_messages(r)
        return JsonResponse({'ok': True})
    except (ValueError, TypeError) as e:
        return JsonResponse({'error': str(e)}, status=400)


@require_POST
def action(request, code):
    pid = player(request, code)
    if not pid:
        return JsonResponse({'error': 'Join this table first.'}, status=403)
    try:
        body = json.loads(request.body)
        if not isinstance(body, dict):
            raise ValueError('Invalid request.')
        with transaction.atomic():
            r = get_object_or_404(Room, code=code)
            if body.get('version') != r.version:
                raise ValueError('The table changed. Please try your move again.')
            if not any(p['id'] == pid for p in r.data['players']):
                return JsonResponse({'error': 'Join this table first.'}, status=403)
            if r.data.get('game') == 'pinochle':
                pinochle.play(r.data, pid, body.get('action'), body)
            else:
                play(r.data, pid, body.get('action'), body.get('index'))
            if not Room.objects.filter(pk=r.pk, version=r.version).update(data=r.data, version=r.version + 1):
                raise ValueError('The table changed. Please try again.')
            RoomMessage.objects.create(room=r, kind='event', author='Server', text=r.data.get('last_move', 'The table changed.'))
            if r.data['phase'] in ('round_over', 'finished'):
                RoomMessage.objects.create(room=r, kind='event', author='Server', text=r.data['message'])
            trim_messages(r)
        return JsonResponse({'ok': True})
    except (ValueError, TypeError) as e:
        return JsonResponse({'error': str(e)}, status=400)
