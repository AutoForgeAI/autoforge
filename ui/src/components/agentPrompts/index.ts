import { prompt as zeusPrompt } from './zeus';
import { prompt as athenaPrompt } from './athena';
import { prompt as apolloPrompt } from './apollo';
import { prompt as hermesPrompt } from './hermes';
import { prompt as artemisPrompt } from './artemis';
import { prompt as hephaestusPrompt } from './hephaestus';
import { prompt as aresPrompt } from './ares';
import { prompt as poseidonPrompt } from './poseidon';
import { prompt as hadesPrompt } from './hades';

export const DEFAULT_PROMPTS: Record<string, string> = {
  Zeus: zeusPrompt,
  Athena: athenaPrompt,
  Apollo: apolloPrompt,
  Hermes: hermesPrompt,
  Artemis: artemisPrompt,
  Hephaestus: hephaestusPrompt,
  Ares: aresPrompt,
  Poseidon: poseidonPrompt,
  Hades: hadesPrompt,
};

// Re-export individual prompts for direct access
export {
  zeusPrompt as zeus,
  athenaPrompt as athena,
  apolloPrompt as apollo,
  hermesPrompt as hermes,
  artemisPrompt as artemis,
  hephaestusPrompt as hephaestus,
  aresPrompt as ares,
  poseidonPrompt as poseidon,
  hadesPrompt as hades,
};

export const QUICK_INSERT_ITEMS = [
  { label: '+ Constraint', text: '\n\n## Additional Constraints\n- ' },
  { label: '+ Responsibility', text: '\n\n## Additional Responsibilities\n- ' },
  { label: '+ Code Style Rule', text: '\n\n## Code Style\n- ' },
  { label: '+ Example', text: '\n\n## Example\n```\n\n```' },
];
