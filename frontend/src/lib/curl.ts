import type { ScanResult } from '../api/types'

/**
 * Port of fireAura() from html_output.py — builds a curl command
 * that reproduces an Aura API request.
 */
export interface CurlOptions {
  proxy?: string | null
  insecure?: boolean
}

export function buildFireAuraCurl(
  scanResult: ScanResult,
  descriptor: string,
  params: Record<string, unknown>,
  options?: CurlOptions,
): string {
  const url = scanResult.aura_url
  const token = scanResult.aura_token || 'undefined'
  const context = scanResult.aura_context || '{}'

  const msg = JSON.stringify({
    actions: [
      {
        id: '123;a',
        descriptor,
        callingDescriptor: 'UNKNOWN',
        params,
      },
    ],
  })

  const body =
    'message=' +
    msg +
    '&aura.context=' +
    encodeURIComponent(context) +
    '&aura.pageURI=/s/' +
    '&aura.token=' +
    encodeURIComponent(token)

  let flags = ''
  if (options?.insecure) flags += ' -k'
  if (options?.proxy) flags += ` --proxy ${options.proxy}`

  let cmd = `curl${flags} -X POST '${url}' -H 'Content-Type: application/x-www-form-urlencoded'`
  if (scanResult.sid) {
    cmd += ` -H 'Cookie: sid=${scanResult.sid}'`
  }
  cmd += ` -d '${body.replace(/'/g, "'\\''")}' | python3 -m json.tool`

  return cmd
}
