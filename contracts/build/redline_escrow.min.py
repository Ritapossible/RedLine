# v0.2.0
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
import datetime
import hashlib
import json
_A = {'amp': '&', 'lt': '<', 'gt': '>', 'quot': '"', 'apos': "'", 'nbsp': ' ', 'rsquo': "'", 'lsquo': "'", 'rdquo': '"', 'ldquo': '"', 'ndash': '-', 'mdash': '-', 'hellip': '...', 'shy': '', 'middot': '*', 'bull': '*'}
_B = {'‘': "'", '’': "'", '‚': "'", '‛': "'", '′': "'", '“': '"', '”': '"', '„': '"', '″': '"', '‐': '-', '‑': '-', '‒': '-', '–': '-', '—': '-', '―': '-', '−': '-', '\xa0': ' ', '\u2007': ' ', '\u202f': ' ', '\u2009': ' ', '\u200a': ' ', '\u2002': ' ', '\u2003': ' ', '\u200b': '', '\u200c': '', '\u200d': '', '\ufeff': '', '\xad': '', '…': '...'}
_C = 40
_D = 600

def _E(name):
 if name.startswith('#'):
  try:
   _a = int(name[2:], 16) if name[1:2] in ('x', 'X') else int(name[1:])
   if 0 < _a < 1114112:
    return chr(_a)
  except ValueError:
   return None
  return None
 return _A.get(name.lower())

def _F(text):
 _f = []
 i = 0
 n = len(text)
 while i < n:
  ch = text[i]
  if ch == '&':
   _c = text.find(';', i + 1, i + 12)
   if _c != -1:
    _b = _E(text[i + 1:_c])
    if _b is not None:
     _f.append(_b)
     i = _c + 1
     continue
  _f.append(ch)
  i += 1
 return ''.join(_f)

def _G(text):
 text = _F(str(text))
 _b = []
 for ch in text:
  _b.append(_B.get(ch, ch))
 return ' '.join(''.join(_b).lower().split())

def passage_error(passage):
 p = _G(passage)
 if len(p) < _C:
  return 'a pinned passage must be at least %d characters' % _C
 if len(p) > _D:
  return 'a pinned passage must be at most %d characters' % _D
 return ''
_H = 'pinning'
_I = 'offered'
_J = 'active'
_K = 'breached'
_L = 'completed'
_M = 'refunded'
_N = (_K, _L, _M)
_O = 'kept'
_P = 'absent'
_Q = 'breach'
_R = 'gone'
_S = (_O, _P, _Q, _R)
_T = (_Q, _R)
_U = (_P, _Q, _R)
_V = 3
_W = 4
_X = 24
_Y = 300
_Z = 60
_AA = 400 * 86400

class _AB(ValueError):
 pass

def _AC(value, context):
 if isinstance(value, bool) or not isinstance(value, int):
  raise _AB('%s: expected an integer, got %r' % (context, value))
 return value

def _AD(value, context='address'):
 _b = str(value).strip().lower()
 if not _b.startswith('0x') or len(_b) != 42:
  raise _AB('%s: not an address: %r' % (context, value))
 for ch in _b[2:]:
  if ch not in '0123456789abcdef':
   raise _AB('%s: not hex: %r' % (context, value))
 return _b

def _AE(cid):
 if not cid or len(cid) > _X:
  return False
 for ch in cid:
  if not (ch.isalnum() or ch in '-_'):
   return False
 return True

def _AF(url):
 u = str(url).strip()
 if not u.startswith('https://') or len(u) > _Y:
  return 'the terms page must be an https URL of at most %d characters' % _Y
 _b = u[8:].split('/')[0]
 for ch in u:
  if ch.isspace() or ch in '?#' or ord(ch) < 33 or (ord(ch) > 126):
   return 'the terms page URL may not contain a query (?), a fragment (#), spaces or non-ASCII characters'
 if '@' in _b or '.' not in _b or _b.startswith('.') or _b.endswith('.'):
  return 'the terms page URL must name a host, with no user name or password'
 return ''

def _AG(*, buyer, vendor, url, passages, value, coverage_seconds, accept_seconds, check_gap_seconds, passage_error):
 _c = []
 try:
  if _AD(buyer, 'buyer') == _AD(vendor, 'vendor'):
   _c.append('the buyer and the vendor must differ')
 except _AB as _d:
  _c.append(str(_d))
 e = _AF(url)
 if e:
  _c.append(e)
 if not isinstance(passages, list) or not 1 <= len(passages) <= _W:
  _c.append('pin 1 to %d passages' % _W)
 else:
  _g = set()
  for p in passages:
   if not isinstance(p, dict) or not isinstance(p.get('id'), str) or (not isinstance(p.get('text'), str)):
    _c.append('each passage is {"id": ..., "text": ...}')
    continue
   _a = p['id'].strip()
   if not _AE(_a):
    _c.append('passage id %r: 1-%d letters, digits, - or _' % (_a[:30], _X))
   elif _a in _g:
    _c.append('passage id %r is used twice' % _a)
   _g.add(_a)
   e = passage_error(p['text'])
   if e:
    _c.append('passage %r: %s' % (_a[:30], e))
 if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
  _c.append('the prepay must be more than 0')
 for _e, v in (('coverage_seconds', coverage_seconds), ('accept_seconds', accept_seconds), ('check_gap_seconds', check_gap_seconds)):
  if isinstance(v, bool) or not isinstance(v, int) or v < _Z or (v > _AA):
   _c.append('%s must be %d-%d seconds' % (_e, _Z, _AA))
 if not _c and _V * int(check_gap_seconds) > int(coverage_seconds):
  _c.append('check_gap_seconds must leave room for %d checks in the coverage period' % _V)
 return _c

def open_cover(*, cover_id, buyer, vendor, url, passages, amount, coverage_seconds, accept_seconds, check_gap_seconds, now):
 return {'id': int(cover_id), 'buyer': _AD(buyer, 'buyer'), 'vendor': _AD(vendor, 'vendor'), 'url': str(url).strip(), 'passages': [{'id': str(p['id']).strip(), 'text': ' '.join(str(p['text']).split())} for p in passages], 'amount': int(amount), 'coverage_seconds': int(coverage_seconds), 'check_gap_seconds': int(check_gap_seconds), 'created_at': int(now), 'accept_by': int(now) + int(accept_seconds), 'state': _H, 'paid': 0, 'seq': 0}

def _AH(cover, at):
 if cover.get('start') is None:
  return 0
 _b = int(at) - int(cover['start'])
 if _b <= 0:
  return 0
 _a = int(cover['coverage_seconds'])
 if _b >= _a:
  return int(cover['amount'])
 return int(cover['amount']) * _b // _a

def _AI(cover, now):
 _a = int(now)
 _b = cover.get('held')
 if _b:
  _a = min(_a, int(_b['from']))
 return _a

def _AJ(credits, who, amount):
 if amount > 0:
  credits[who] = credits.get(who, 0) + amount

def _AK(cover, now):
 credits = {}
 if cover['state'] != _J:
  return credits
 _a = _AH(cover, _AI(cover, now)) - int(cover['paid'])
 if _a > 0:
  cover['paid'] = int(cover['paid']) + _a
  _AJ(credits, cover['vendor'], _a)
 return credits

def _AL(cover, state, at, now):
 credits = {}
 _a = max(int(cover['paid']), _AH(cover, at))
 _AJ(credits, cover['vendor'], _a - int(cover['paid']))
 _AJ(credits, cover['buyer'], int(cover['amount']) - _a)
 cover['paid'] = _a
 cover['refunded'] = int(cover['amount']) - _a
 cover['state'] = state
 cover['closed_at'] = int(now)
 cover['closed_as_of'] = int(at)
 cover.pop('held', None)
 return credits

def _AM(cover, now, why):
 credits = {}
 _AJ(credits, cover['buyer'], int(cover['amount']))
 cover['refunded'] = int(cover['amount'])
 cover['state'] = _M
 cover['closed_at'] = int(now)
 cover['why'] = str(why)[:80]
 return credits

def _AN(cover, *, ok, at, now, reason=''):
 if cover['state'] != _H:
  raise _AB('cover %d is not being pinned' % int(cover['id']))
 if int(at) > int(cover['accept_by']):
  raise _AB('the pin came after the acceptance deadline')
 if ok:
  cover['state'] = _I
  cover['pinned_at'] = int(at)
  return {}
 return _AM(cover, now, 'not pinned: ' + str(reason))

def accept(cover, *, by, now):
 if _AD(by) != cover['vendor']:
  raise _AB('only the vendor may accept')
 if cover['state'] != _I:
  raise _AB('cover %d is not offered (it is %s)' % (int(cover['id']), cover['state']))
 if int(now) > int(cover['accept_by']):
  raise _AB('the acceptance deadline has passed')
 cover['state'] = _J
 cover['start'] = int(now)
 cover['end'] = int(now) + int(cover['coverage_seconds'])

def cancel(cover, *, by, now):
 if _AD(by) != cover['buyer']:
  raise _AB('only the buyer may cancel')
 if cover['state'] not in (_H, _I):
  raise _AB('cover %d can no longer be cancelled (it is %s)' % (int(cover['id']), cover['state']))
 return _AM(cover, now, 'cancelled by the buyer')

def _AO(cover, *, seq, kind, at, since, now):
 if cover['state'] != _J:
  raise _AB('cover %d is not active' % int(cover['id']))
 if kind not in _S:
  raise _AB('unknown check kind %r' % kind)
 seq = _AC(seq, 'seq')
 if int(at) > int(cover['end']):
  raise _AB('the check came after the cover ended')
 _a = cover.get('held')
 if seq < int(cover['seq']):
  return {}
 if _a and int(_a['seq']) != seq and (_a['kind'] in _T):
  return {}
 credits = _AK(cover, at) if not _a else {}
 cover['seq'] = seq
 cover['last_check'] = {'seq': seq, 'kind': kind, 'at': int(at)}
 if kind in _U:
  _b = int(since) if kind in (_P, _R) else int(at)
  if _a and int(_a['seq']) != seq:
   _b = min(_b, int(_a['from']))
  cover['held'] = {'seq': seq, 'kind': kind, 'from': max(min(_b, int(at)), int(cover['start'])), 'noted_at': int(now)}
 else:
  cover.pop('held', None)
 return credits

def _AP(cover, now, appeal_seconds):
 now = int(now)
 _b = cover['state']
 if _b in (_H, _I):
  if now > int(cover['accept_by']):
   return _AM(cover, now, 'not accepted in time')
  return {}
 if _b != _J:
  return {}
 _a = cover.get('held')
 if _a and _a['kind'] in _T and (now >= int(_a['noted_at']) + int(appeal_seconds)):
  return _AL(cover, _K, int(_a['from']), now)
 if now > int(cover['end']) + int(appeal_seconds):
  if _a and _a['kind'] in _T:
   return _AL(cover, _K, int(_a['from']), now)
  if _a and _a['kind'] == _P:
   return _AL(cover, _K, int(_a['from']), now)
  return _AL(cover, _L, int(cover['end']), now)
 return _AK(cover, now)

def _AQ(cover):
 if cover['state'] in _N:
  return 0
 return int(cover['amount']) - int(cover['paid'])

def _AR(value, digits):
 s = str(value).lower()
 return len(s) == 2 + digits and s.startswith('0x') and all((c in '0123456789abcdef' for c in s[2:]))

class RedLineEscrow(gl.Contract):
 release: str
 watcher: str
 appeal_seconds: u256
 cover_count: u256
 covers: TreeMap[u256, str]
 escrows: TreeMap[u256, str]
 refusals: TreeMap[str, str]

 def __init__(self, watcher: str, appeal_seconds: int):
  if int(appeal_seconds) < 0 or int(appeal_seconds) > _AA:
   raise Exception('[EXPECTED] the appeal window is 0-%d seconds' % _AA)
  self.release = 'redline-escrow/1'
  self.watcher = _AD(watcher, 'watcher')
  self.appeal_seconds = u256(int(appeal_seconds))
  self.cover_count = u256(0)

 def _now(self) -> int:
  return int(datetime.datetime.now().timestamp())

 def _me(self) -> str:
  return str(gl.message.sender_address).lower()

 def _load(self, cover_id: int) -> dict:
  if int(cover_id) < 0 or int(cover_id) >= int(self.cover_count):
   raise Exception('[EXPECTED] unknown cover')
  return json.loads(self.covers[u256(int(cover_id))])

 def _save(self, cover: dict) -> None:
  self.covers[u256(int(cover['id']))] = json.dumps(cover)

 def _from_watcher(self) -> None:
  if self._me() != self.watcher:
   raise Exception('[EXPECTED] only the watcher contract reports on a cover')

 @gl.public.write
 def open_cover(self, vendor: str, url: str, passages_json: str, amount: int, coverage_seconds: int, accept_seconds: int, check_gap_seconds: int, chain_id: int, escrow_uid: str, arbiter: str) -> int:
  me = self._me()
  try:
   _e = json.loads(str(passages_json))
  except Exception:
   _e = None
  _c = ['the passages are not valid JSON'] if _e is None else _AG(buyer=me, vendor=str(vendor), url=str(url), passages=_e, value=int(amount), coverage_seconds=int(coverage_seconds), accept_seconds=int(accept_seconds), check_gap_seconds=int(check_gap_seconds), passage_error=passage_error)
  if int(chain_id) <= 0:
   _c.append("the escrow's chain id must be more than 0")
  if not _AR(escrow_uid, 64):
   _c.append('the escrow id is 0x and 64 hex digits')
  if not _AR(arbiter, 40):
   _c.append('the arbiter is an address')
  if _c:
   self.refusals[me] = json.dumps({'reason': '; '.join(_c)[:600], 'at': self._now()})
   return -1
  _b = int(self.cover_count)
  _a = open_cover(cover_id=_b, buyer=me, vendor=str(vendor), url=str(url), passages=_e, amount=int(amount), coverage_seconds=int(coverage_seconds), accept_seconds=int(accept_seconds), check_gap_seconds=int(check_gap_seconds), now=self._now())
  self._save(_a)
  self.escrows[u256(_b)] = json.dumps({'chain_id': int(chain_id), 'escrow': str(escrow_uid).lower(), 'arbiter': str(arbiter).lower(), 'fulfillment': ''})
  self.cover_count = u256(_b + 1)
  gl.get_contract_at(Address(self.watcher)).emit(on='accepted').pin(str(self.address).lower(), _b)
  return _b

 @gl.public.write
 def note_pin(self, cover_id: int, ok: bool, at: int, reason: str) -> None:
  self._from_watcher()
  _a = self._load(cover_id)
  try:
   _AN(_a, ok=bool(ok), at=int(at), now=self._now(), reason=str(reason))
  except _AB as _b:
   raise Exception('[EXPECTED] ' + str(_b))
  self._save(_a)

 @gl.public.write
 def accept(self, cover_id: int, fulfillment_uid: str) -> None:
  if not _AR(fulfillment_uid, 64):
   raise Exception('[EXPECTED] the fulfillment id is 0x and 64 hex digits')
  _a = self._load(cover_id)
  try:
   accept(_a, by=self._me(), now=self._now())
  except _AB as _c:
   raise Exception('[EXPECTED] ' + str(_c))
  self._save(_a)
  _b = json.loads(self.escrows[u256(int(cover_id))])
  _b['fulfillment'] = str(fulfillment_uid).lower()
  self.escrows[u256(int(cover_id))] = json.dumps(_b)

 @gl.public.write
 def cancel(self, cover_id: int) -> None:
  _a = self._load(cover_id)
  try:
   cancel(_a, by=self._me(), now=self._now())
  except _AB as _b:
   raise Exception('[EXPECTED] ' + str(_b))
  self._save(_a)

 @gl.public.write
 def note_check(self, cover_id: int, seq: int, kind: str, at: int, since: int) -> None:
  self._from_watcher()
  _a = self._load(cover_id)
  try:
   _AO(_a, seq=int(seq), kind=str(kind), at=int(at), since=int(since), now=self._now())
  except _AB as _b:
   raise Exception('[EXPECTED] ' + str(_b))
  self._save(_a)

 @gl.public.write
 def settle(self, cover_id: int) -> None:
  _a = self._load(cover_id)
  _AP(_a, self._now(), int(self.appeal_seconds))
  self._save(_a)

 @gl.public.view
 def get_cover(self, cover_id: int) -> str:
  _a = self._load(cover_id)
  _a['now'] = self._now()
  _a['outstanding'] = _AQ(_a)
  return json.dumps(_a)

 @gl.public.view
 def ruling_of(self, cover_id: int) -> str:
  _a = self._load(cover_id)
  _b = json.loads(self.escrows[u256(int(cover_id))])
  _c = _a['state'] in _N
  return json.dumps({'cover': int(_a['id']), 'state': _a['state'], 'final': _c, 'started': _a.get('start') is not None, 'amount': int(_a['amount']), 'vendor': _a['vendor'], 'buyer': _a['buyer'], 'vendor_amount': int(_a['paid']) if _c else 0, 'buyer_amount': int(_a.get('refunded', 0)) if _c else 0, 'as_of': int(_a.get('closed_as_of', _a.get('closed_at', 0))) if _c else 0, 'chain_id': _b['chain_id'], 'escrow': _b['escrow'], 'arbiter': _b['arbiter'], 'fulfillment': _b['fulfillment']})

 @gl.public.view
 def refusal_of(self, address: str) -> str:
  return self.refusals.get(str(address).lower(), '{}')

 @gl.public.view
 def status(self) -> str:
  return json.dumps({'release': self.release, 'watcher': self.watcher, 'appeal_seconds': int(self.appeal_seconds), 'covers': int(self.cover_count)})
