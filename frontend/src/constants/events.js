// Shared custom DOM event names for cross-component notifications that
// don't warrant a full Context — e.g. telling Layout.jsx's sidebar badge
// to refetch immediately after an action changes what it's counting,
// instead of waiting for its periodic poll.
export const PENDING_APPROVALS_CHANGED_EVENT = 'pending-approvals-changed';
