// One definition of where the API lives. This was repeated in five components,
// each with its own copy of the comment explaining it, so a change meant
// finding all five.
//
// Relative on purpose: the page works from any device on the network. An
// absolute localhost URL would resolve to whatever machine the browser is on
// rather than the Pi.
export const API_BASE = '/api/v1'
