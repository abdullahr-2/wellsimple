// A small client for Databricks SQL Statement Execution, using service-principal OAuth.
const HOST = 'https://dbc-3f1b90dd-86d2.cloud.databricks.com';
const CLIENT_ID = '1976bc53-bed5-4eb3-85d3-d30c486dfa78';
const WAREHOUSE = '7a37fcfd214d743a';
let cachedToken;

async function token(secret) {
  if (cachedToken && cachedToken.expires > Date.now() + 60000) return cachedToken.value;
  const response = await fetch(HOST + '/oidc/v1/token', {
    method: 'POST',
    headers: {'Content-Type': 'application/x-www-form-urlencoded',
      Authorization: 'Basic ' + btoa(CLIENT_ID + ':' + secret)},
    body: new URLSearchParams({grant_type: 'client_credentials', scope: 'all-apis'})
  });
  if (!response.ok) throw new Error('Databricks authentication failed');
  const value = await response.json();
  cachedToken = {value: value.access_token, expires: Date.now() + value.expires_in * 1000};
  return cachedToken.value;
}

export async function query(secret, statement, parameters = []) {
  const authorization = 'Bearer ' + await token(secret);
  async function call(path, options = {}) {
    const response = await fetch(HOST + path, {
      ...options, headers: {...options.headers, Authorization: authorization}
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error('Databricks SQL request failed (' + response.status + '): ' + (error.message || error.error_code || 'unknown'));
    }
    return response.json();
  }
  let result = await call('/api/2.0/sql/statements', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({warehouse_id: WAREHOUSE, statement, parameters, wait_timeout: '30s'})
  });
  while (['PENDING', 'RUNNING'].includes(result.status.state)) {
    await new Promise(resolve => setTimeout(resolve, 1000));
    result = await call('/api/2.0/sql/statements/' + result.statement_id);
  }
  if (result.status.state !== 'SUCCEEDED') throw new Error('Databricks SQL failed: ' + (result.status.error?.message || result.status.state));
  if (result.manifest?.truncated) throw new Error('Databricks SQL result was truncated');
  const columns = result.manifest?.schema?.columns || [];
  const values = [...(result.result?.data_array || [])];
  let next = result.result?.next_chunk_index;
  while (next != null) {
    const chunk = await call('/api/2.0/sql/statements/' + result.statement_id + '/result/chunks/' + next);
    values.push(...(chunk.data_array || []));
    next = chunk.next_chunk_index;
  }
  return values.map(row => Object.fromEntries(columns.map((c, i) => [c.name, row[i]])));
}
