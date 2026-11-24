// The field has seven columns and six ranks. Coordinates refer to the foot of
// each figure, both here and in the isometric renderer.
export const TACTIC_COLS = 7;
export const TACTIC_ROWS = 6;
const tacticMaps = [
  ['#..+..#', '..#...+', '.+.....', '...+...', '....#..', '+...+.#'],
  ['#....+#', '.+#..+.', '.....#.', '...+...', '.#...+.', '#..+..#'],
  ['.+#...#', '+...#..', '..+....', '....+..', '#..#...', '.+....#'],
  ['#...+.#', '..#....', '+....+.', '...+...', '..#....', '.+..#.+'],
  ['#.+...#', '...#.+.', '.+.....', '....+..', '..#....', '+....#.'],
  ['.+..#..', '#..+...', '....+.#', '...+...', '.#....+', '..+.#..'],
  ['#.+...#', '.#...+.', '..+....', '...+...', '+...#..', '#..+..#']
];
const tacticSteps = [[-1,0],[0,-1],[1,0],[0,1]];
const tacticDistance = (a, b) => Math.abs(a.x - b.x) + Math.abs(a.y - b.y);
const tacticMatch = (a, b) => a.x === b.x && a.y === b.y;
const tacticKey = p => p.y * TACTIC_COLS + p.x;

export function tacticalTerrain(state, x, y) {
  const row = state.battle.boss ? TACTIC_ROWS - 1 - y : y;
  return tacticMaps[state.chapter]?.[row]?.[x] ?? '#';
}

function tacticSquad(state) {
  const members = state.met.slice(state.chapter === 6 ? -2 : -1);
  return ['hero', ...members];
}

export function createTacticalField(state) {
  const members = tacticSquad(state);
  const positions = [[2,3],[1,3],[2,2]];
  // Both halves reserve a central corridor for deployment. A boss's board
  // mirrors the corridor along with its deployment points.
  const unit = (id, x, y) => ({ id, x, y:state.battle.boss ? 5-y : y });
  return {
    allies:members.map((id, i) => unit(id, ...positions[i])),
    leader:unit('leader', 5,3),
    echo:state.battle.boss ? { ...unit('echo', 5,1), hp:tacticalEchoMax(state) } : null,
    active:'hero', target:'leader', moved:[], acted:[], guard:0, silence:false
  };
}

export function tacticalEchoMax(state) { return Math.ceil(state.battle.maxHp * .12); }

export function tacticalUnits(state) {
  const field = state.battle.field;
  return [...field.allies, field.leader, ...(field.echo?.hp > 0 ? [field.echo] : [])];
}
export function tacticalActive(state) {
  return state.battle.field.allies.find(a => a.id === state.battle.field.active);
}
export function tacticalTarget(state) {
  const field = state.battle.field;
  return field.target === 'echo' && field.echo?.hp > 0 ? field.echo : field.leader;
}
export function tacticalRange(unit) { return unit.id === 'hero' ? 1 : 2; }

// Breadth-first traversal gives actual path costs and never crosses another unit.
function tacticPaths(state, unit) {
  const blocked = new Set(tacticalUnits(state).filter(u => u.id !== unit.id).map(tacticKey));
  const origin = {x:unit.x, y:unit.y, cost:0, parent:null};
  const queue = [origin], visited = new Set([tacticKey(origin)]);
  for (let i = 0; i < queue.length; i++) {
    const cell = queue[i];
    for (const [dx,dy] of tacticSteps) {
      const p = {x:cell.x+dx, y:cell.y+dy, cost:cell.cost+1, parent:cell};
      if (tacticalTerrain(state,p.x,p.y) === '#' || blocked.has(tacticKey(p)) || visited.has(tacticKey(p))) continue;
      queue.push(p); visited.add(tacticKey(p));
    }
  }
  return queue;
}

export function tacticalMoves(state) {
  const unit = tacticalActive(state), field = state.battle.field;
  if (field.moved.includes(unit.id) || field.acted.includes(unit.id)) return [];
  return tacticPaths(state, unit).filter(p => p.cost > 0 && p.cost <= 3);
}

function tacticFiringPoint(state, unit, target, range, budget) {
  const spots = tacticPaths(state,unit).filter(p => p.cost <= budget && tacticDistance(p,target) <= range);
  return spots.sort((a,b) => a.cost - b.cost)[0] || null;
}

export function tacticalApproach(state, range) {
  const unit = tacticalActive(state), target = tacticalTarget(state);
  return tacticFiringPoint(state, unit, target, range, state.battle.field.moved.includes(unit.id) ? 0 : 3);
}

export function tacticalFlank(state) {
  const unit = tacticalActive(state), target = tacticalTarget(state);
  if (tacticDistance(unit, target) !== 1) return false;
  return state.battle.field.allies.some(a => a.id !== unit.id && a.x + unit.x === target.x * 2 && a.y + unit.y === target.y * 2);
}

export function tacticalCommand(state, action) {
  const f = state.battle.field;
  if (action.command === 'select' && f.allies.some(a => a.id === action.id) && !f.acted.includes(action.id)) {
    f.active = action.id;
  } else if (action.command === 'target' && (action.id === 'leader' || (action.id === 'echo' && f.echo?.hp > 0))) {
    f.target = action.id;
  } else if (action.command === 'move') {
    const cell = tacticalMoves(state).find(p => p.x === action.x && p.y === action.y);
    if (cell) {
      const unit = tacticalActive(state);
      unit.x = cell.x; unit.y = cell.y; f.moved.push(unit.id);
    }
  }
}

// Walk toward a reachable attack position. If allies block all adjacent tiles,
// take the shortest available approach to a different ally instead.
export function advanceTacticalEnemy(state, enemy) {
  const paths = tacticPaths(state,enemy);
  let best = null;
  for (const ally of state.battle.field.allies) {
    for (const p of paths) {
      if (tacticDistance(p,ally) === 1 && (!best || p.cost < best.spot.cost)) best = {ally,spot:p};
    }
  }
  if (!best) return null;
  let dest = best.spot;
  while (dest.cost > 2) dest = dest.parent;
  enemy.x = dest.x; enemy.y = dest.y;
  return tacticDistance(enemy, best.ally) === 1 ? best.ally : null;
}

export function restoreTacticalField(state, field) {
  if (field === undefined) return createTacticalField(state);
  const expected = createTacticalField(state);
  const validUnit = (u, id) => u && u.id === id && Number.isInteger(u.x) && Number.isInteger(u.y) && tacticalTerrain(state,u.x,u.y) !== '#';
  const squad = tacticSquad(state);
  const validList = a => Array.isArray(a) && new Set(a).size === a.length && a.every(id => squad.includes(id));
  if (!field || !Array.isArray(field.allies) || field.allies.length !== squad.length ||
      !field.allies.every((u,i) => validUnit(u,squad[i])) || !validUnit(field.leader,'leader') ||
      !validList(field.moved) || !validList(field.acted) || field.acted.includes('hero') ||
      !squad.includes(field.active) || field.acted.includes(field.active) ||
      ![0,.45,.76,.85].includes(field.guard) || typeof field.silence !== 'boolean') return null;
  if (expected.echo ? (!validUnit(field.echo,'echo') || !Number.isInteger(field.echo.hp) || field.echo.hp < 0 || field.echo.hp > tacticalEchoMax(state)) : field.echo !== null) return null;
  if (field.target !== 'leader' && !(field.target === 'echo' && field.echo?.hp > 0)) return null;
  const units = [...field.allies, field.leader, ...(field.echo?.hp > 0 ? [field.echo] : [])];
  if (new Set(units.map(tacticKey)).size !== units.length) return null;
  const coords = u => ({id:u.id, x:u.x, y:u.y});
  return {allies:field.allies.map(coords), leader:coords(field.leader), echo:field.echo && {...coords(field.echo),hp:field.echo.hp},
    active:field.active,target:field.target,moved:[...field.moved],acted:[...field.acted],guard:field.guard,silence:field.silence};
}
