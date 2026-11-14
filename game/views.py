import json
import secrets
import string
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from .models import Room
from .engine import play, score


def home(request):
    return render(request, 'home.html')


def name(request):
    value = request.POST.get('name', '').strip()
    if not 1 <= len(value) <= 24:
        raise ValueError('Enter a name between 1 and 24 characters.')
    return value


def player(request, code):
    return request.session.get('rooms', {}).get(code)


def remember(request, code, pid):
    rooms = request.session.get('rooms', {})
    rooms[code] = pid
    request.session['rooms'] = rooms


@require_POST
def create(request):
    try:
        n = name(request)
    except ValueError as e:
        return render(request, 'home.html', {'error': str(e)}, status=400)
    code = ''.join(secrets.choice(string.ascii_uppercase.replace('O', '').replace('I', '')) for _ in range(8))
    pid = secrets.token_urlsafe(24)
    Room.objects.create(code=code, data={'phase': 'lobby', 'round': 0, 'players': [{'id': pid, 'name': n, 'lives': 3, 'hand': []}], 'message': 'The best seat is the one with family.'})
    remember(request, code, pid)
    return redirect('/room/' + code + '/')


@require_POST
def join(request):
    code = request.POST.get('code', '').strip().upper()
    try:
        n = name(request)
        with transaction.atomic():
            r = Room.objects.filter(code=code).first()
            if not r:
                raise ValueError('That table was not found. Check the room code.')
            if player(request, code):
                return redirect('/room/' + code + '/')
            g = r.data
            if g['phase'] != 'lobby' or len(g['players']) >= 6:
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
        return render(request, 'home.html', {'error': str(e), 'code': code}, status=400)


def room(request, code):
    r = get_object_or_404(Room, code=code)
    if not player(request, code):
        return render(request, 'home.html', {'code': code})
    return render(request, 'room.html', {'code': r.code})


def state(request, code):
    r = get_object_or_404(Room, code=code)
    pid = player(request, code)
    if not pid or not any(p['id'] == pid for p in r.data['players']):
        return JsonResponse({'error': 'Join this table first.'}, status=403)
    g = r.data
    players = [{'name': p['name'], 'lives': p['lives'], 'you': p['id'] == pid, 'host': i == 0, 'turn': p['id'] == g.get('turn'), 'knocked': p['id'] == g.get('knocked'), 'hand': p['hand'] if p['id'] == pid else []} for i, p in enumerate(g['players'])]
    hand = next(p['hand'] for p in players if p['you'])
    response = JsonResponse({'version': r.version, 'phase': g['phase'], 'round': g['round'], 'players': players, 'your_turn': g.get('turn') == pid, 'drawn': g.get('drawn', False), 'knocked': bool(g.get('knocked')), 'top': g.get('discard', [None])[-1] if g.get('discard') else None, 'deck_count': len(g.get('deck', [])), 'message': g['message'], 'score': score(hand) if hand else 0, 'result': g.get('result', [])})
    response['Cache-Control'] = 'no-store'
    return response


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
            play(r.data, pid, body.get('action'), body.get('index'))
            if not Room.objects.filter(pk=r.pk, version=r.version).update(data=r.data, version=r.version + 1):
                raise ValueError('The table changed. Please try again.')
        return JsonResponse({'ok': True})
    except (ValueError, TypeError) as e:
        return JsonResponse({'error': str(e)}, status=400)
