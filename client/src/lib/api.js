const fetchWrapper = async (url, body, method) => {
  if (!body) {
    return await fetch(url, {
      method: 'GET', cache: "no-cache"
    });
  }
  return await fetch(url, {
    method, cache: "no-cache",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

class SPARQLQueryDispatcher {
  constructor( endpoint ) {
    this.endpoint = endpoint;
  }

  query( sparqlQuery ) {
    const fullUrl = this.endpoint + '?query=' + encodeURIComponent( sparqlQuery );
    const headers = { 'Accept': 'application/sparql-results+json' };

    return fetch( fullUrl, { headers } ).then( body => body.json() );
  }
}

const getGenerationYears = async (wiki) => {

  const endpoint = `https://${wiki}/sparql`;
  const sparqlQuery = `SELECT ?num ?date
  WHERE
  {
    ?gen wdt:P31 wd:Q3759600;
         p:P31 ?series;
         OPTIONAL { 
           ?series pq:P1545 ?num;
         }
         OPTIONAL { ?gen wdt:P571 ?date }
  }`;

  const queryDispatcher = new SPARQLQueryDispatcher( endpoint );
  const { results }  = await queryDispatcher.query( sparqlQuery );
  return results.bindings.map(({ num, date }) => {
    const year_str = date.value.split('-')[0];
    const now = new Date().getFullYear(); 
    return { 
      n: parseInt(num.value) || 0,
      year: parseInt(year_str) || now,
    }
  }).sort((a,b) => a.year - b.year);
}

const getLatestMetadata = async (root, wiki) => {
  const url = `${root}/api/latest_metadata`;
  const gen_years = await getGenerationYears(wiki);
  const response = await fetchWrapper(url);
  const out = (await response.json()) || {
    defaults: { max_gen: 1 }
  };
  const { max_gen } = out.defaults;
  return { max_gen, gen_years };
}

const getValidCombos = async (root, max_gen=null) => {
  const url = `${root}/api/valid_combos` + (
    max_gen ? `?max_gen=${max_gen}` : ''
  );
  const response = await fetchWrapper(url);
  const out = (await response.json()) || [];
  return out.map(v => v?.combo).filter(v => v);
}

const getRegions = async (root, max_gen=null) => {
  const url = `${root}/api/regions` + (
    max_gen ? `?max_gen=${max_gen}` : ''
  );
  const response = await fetchWrapper(url);
  const out = (await response.json()) || [];
  return out.map(v => v?.region).filter(v => v);
}

const getForms = async (root, guess) => {
  const params = new URLSearchParams();
  params.append('dexn', guess);
  const url = `${root}/api/forms?${params.toString()}`;
  const response = await fetchWrapper(url);
  const out = (await response.json()) || [];
  return out.map(v => v?.form).filter(v => v);
}

const getMatches = async (root, guess, max_gen=null) => {
  const params = new URLSearchParams();
  params.append('guess', guess);
  if (max_gen != null) params.append('max_gen', max_gen);
  const url = `${root}/api/matches?${params.toString()}`;
  const response = await fetchWrapper(url);
  const out = (await response.json()) || [];
  return out.map(v => v?.pokemon).filter(v => v);
}

const testGuess = async (root, identifier, conditions) => {
  const params = new URLSearchParams();
  params.append('identifier', identifier);
  params.append('conditions', conditions.join(','));
  const url = `${root}/api/test?${params.toString()}`;
  const response = await fetchWrapper(url);
  const out = (await response.json()) || {};
  return out?.ok || false;
}

export { testGuess, getMatches, getForms, getRegions, getValidCombos, getLatestMetadata };
