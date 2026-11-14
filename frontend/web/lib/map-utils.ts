import type { Address } from '@/lib/types'

export interface MarkerConfig {
  lngLat: [number, number]
  popup: HTMLElement
  count: number
}

export function addressToMarker(address: Address): MarkerConfig {
  return {
    lngLat: [address.lng, address.lat],
    popup: addressPopup(address),
    count: address.count,
  }
}

// Addresses come from parsed PDFs and the geocoder, so they are set as text, never as HTML.
function addressPopup(address: Address): HTMLElement {
  const displayName = address.normalized_address ?? address.raw_address
  const plural = address.count === 1 ? 'incident' : 'incidents'

  const name = document.createElement('strong')
  name.textContent = displayName

  const popup = document.createElement('div')
  popup.append(name, document.createElement('br'), `${address.count} ${plural}`)
  return popup
}
