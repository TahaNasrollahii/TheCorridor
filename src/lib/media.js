// Attachment helpers for the Mini App. Files are read to base64 and sent in the
// JSON body of the `send` action. Vercel caps a request body at ~4.5 MB and
// base64 adds ~33%, so we hold raw files under ~3 MB (matched server-side).

export const MAX_MEDIA_BYTES = 3_000_000

export function tooBig(sizeBytes) {
  return sizeBytes > MAX_MEDIA_BYTES
}

// Read a File/Blob into raw base64 (no data: prefix), the shape the API wants.
export function toBase64(fileOrBlob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = String(reader.result || '')
      const comma = result.indexOf(',')
      resolve(comma >= 0 ? result.slice(comma + 1) : result)
    }
    reader.onerror = () => reject(new Error('the file could not be read'))
    reader.readAsDataURL(fileOrBlob)
  })
}
