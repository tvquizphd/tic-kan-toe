// Map from generation to Map of badges
// https://raw.githubusercontent.com/PokeAPI/pokeapi/3cb275c0b5da2c6b3299fb6c965b86d9cb6fe37c/data/v2/csv/gym_badges.csv
const gen_gym_badges = new Map([
  [1, new Map([
    [1,"boulder"],[2,"cascade"],[3,"thunder"],[4,"rainbow"],[5,"soul"],[6,"marsh"],[7,"volcano"],[8,"earth"]
  ])],
  [2, new Map([
    [9,"zephyr"],[10,"hive"],[11,"plain"],[12,"fog"],[13,"storm"],[14,"mineral"],[15,"glacier"],[16,"rising"]
  ])],
  [3, new Map([
    [17,"stone"],[18,"knuckle"],[19,"dynamo"],[20,"heat"],[21,"balance"],[22,"feather"],[23,"mind"],[24,"rain"]
  ])],
  [4, new Map([
    [25,"coal"],[26,"forest"],[27,"cobble"],[28,"fen"],[29,"relic"],[30,"mine"],[31,"icicle"],[32,"beacon"]
  ])],
  [5, new Map([
    [33,"trio"],[34,"basic"],[35,"insect"],[36,"bolt"],[37,"quake"],[38,"jet"],[39,"freeze"],[40,"legend"]
  ])],
  [6, new Map([
    [41,"bug"],[42,"cliff"],[43,"rumble"],[44,"plant"],[45,"voltage"],[46,"fairy"],[47,"psychic"],[48,"iceberg"]
  ])],
  [8, new Map([
    [49,"grass"],[50,"water"],[51,"fire"],[52,"fighting"],[53,"ghost"],[54,"fairy"],[55,"rock"],[56,"ice"],[57,"dark"],[58,"dragon"]
  ])]
]);

const max_gym_gen = [
  ...gen_gym_badges.keys()
].slice(-1)[0]

const to_random_badge = (max_gen) => {
  const max = to_max_gym_badge(max_gen);
  const min = to_min_gym_badge(max_gen);
  const rational = Math.random() * (max-min);
  return Math.ceil(rational) + min;
}

const nearest_gen = (key) => {
  return [...gen_gym_badges.keys()].sort((a,b) => {
    return Math.abs(a-key)-Math.abs(b-key);
  })[0];
}

const to_max_gym_badge = (generation) => {
  const gen = nearest_gen(generation);
  return [
    ...gen_gym_badges.get(gen).keys()
  ].slice(-1)[0]
}

const to_min_gym_badge = (generation) => {
  const gen = nearest_gen(generation);
  return [
    ...gen_gym_badges.get(gen).keys()
  ][0]
}

const all_gym_badges = [...gen_gym_badges.values()].reduce(
  (map, gen) => {
    [...gen].forEach(([k, v]) => map.set(k, v));
    return map;
  },
  new Map()
);

const badge_info = {
  gen_gym_badges, max_gym_gen,
  all_gym_badges
}

export {
  badge_info,
  to_random_badge,
  to_min_gym_badge,
  to_max_gym_badge
}
