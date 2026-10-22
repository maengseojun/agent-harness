// Stub (motion-studio): sound.js imports openFilm for its browser probe, which motion-studio does not use.
import { OmError } from './project.js';
export const openFilm = async () => { throw new OmError('openFilm is not available in motion-studio; pass cues as JSON'); };
