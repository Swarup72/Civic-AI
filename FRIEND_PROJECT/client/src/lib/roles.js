// Single source of truth for the four CivicAI roles.
// Used by the signup form (role picker) and ProtectedRoute (access checks).
export const ROLES = {
  CITIZEN: 'citizen',
  GOVERNMENT: 'government',
  NGO: 'ngo',
  ADMIN: 'admin',
}

export const ROLE_LIST = Object.values(ROLES)

export const ROLE_LABELS = {
  [ROLES.CITIZEN]: 'Citizen',
  [ROLES.GOVERNMENT]: 'Government Official',
  [ROLES.NGO]: 'NGO Representative',
  [ROLES.ADMIN]: 'Admin',
}

// Where each role lands after login.
export const ROLE_HOME_PATH = {
  [ROLES.CITIZEN]: '/citizen',
  [ROLES.GOVERNMENT]: '/government',
  [ROLES.NGO]: '/ngo',
  [ROLES.ADMIN]: '/admin',
}
