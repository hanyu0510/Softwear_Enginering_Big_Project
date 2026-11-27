export function validEmail(email) {
  const [local, domain] = email.split('@')
  return email.length <= 254 && !!domain && local.length <= 64 &&
    !local.startsWith('.') && !local.endsWith('.') && !local.includes('..') &&
    /^[a-z0-9.!#$%&'*+/=?^_{|}~-]+@[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+$/i.test(email.replaceAll('\x60', '_')) &&
    domain.split('.').every(label => label.length <= 63) && !domain.includes('\x60')
}
