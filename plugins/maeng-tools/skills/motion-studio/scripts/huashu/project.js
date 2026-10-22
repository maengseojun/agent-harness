// Stub (motion-studio): the vendored sound engine and qa import OmError from here. The om project
// format (readSource/writeSource) is not vendored; motion-studio passes cues as JSON instead.
export class OmError extends Error {
  constructor(message, status = 400) { super(message); this.status = status; }
}
const unsupported = (name) => () => { throw new OmError(`${name} is not available in motion-studio; use scripts/studio.mjs`); };
export const readSource = unsupported('readSource');
export const writeSource = unsupported('writeSource');
