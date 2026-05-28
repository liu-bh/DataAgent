import { setupWorker } from 'msw/browser';
import { handlers } from './handlers';

/** MSW worker，仅在开发模式下启用 */
const worker = import.meta.env.DEV
  ? setupWorker(...handlers)
  : { start: () => Promise.resolve() };

export { worker };
