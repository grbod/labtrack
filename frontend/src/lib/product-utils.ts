/**
 * Generates display name from product fields.
 * Format: "Brand Product Name Flavor Size (VX)"
 * Empty optional fields are skipped.
 *
 * @param brand - Product brand (required)
 * @param productName - Product name (required)
 * @param flavor - Product flavor (optional)
 * @param size - Product size (optional)
 * @param version - Version number (optional) - appends "(VX)" to the end
 * @returns Generated display name string
 */
export function generateDisplayName(
  brand: string,
  productName: string,
  flavor?: string,
  size?: string,
  version?: string
): string {
  const parts = [brand, productName]
  if (flavor?.trim()) parts.push(flavor.trim())
  if (size?.trim()) parts.push(size.trim())

  let displayName = parts.join(" ")

  if (version?.trim()) {
    displayName += ` (V${version.trim()})`
  }

  return displayName
}
