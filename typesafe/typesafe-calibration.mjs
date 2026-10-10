import { createTypesafe, choice, evaluate } from '@ruvector/typesafe';
import { performance } from 'node:perf_hooks';

const criteria = {
  cloud: {
    what: 'cloud platform, AWS, infrastructure, migration, identity, networking or deployment',
    not_for: 'payments operations or artificial intelligence model evaluation',
    examples: ['AWS account vending failed', 'migration wave needs a landing zone'],
  },
  payments: {
    what: 'card payment, settlement, billing, pricing, refund or transaction operations',
    not_for: 'cloud infrastructure or machine learning evaluation',
    examples: ['duplicate card charge', 'settlement file did not arrive'],
  },
  ai: {
    what: 'AI model, embeddings, evaluation, calibration, agent, inference or vector search',
    not_for: 'payment operations or general cloud infrastructure',
    examples: ['confidence calibration regressed', 'vector retrieval quality dropped'],
  },
  other: 'catch-all; its text is ignored when catchAll is configured',
};

const questions = { route: choice(criteria, { instructions: 'Choose the specialist team that should own this request.' }) };

const labelled = [
  ['AWS Control Tower guardrail blocks the new account', 'cloud'],
  ['The VPC route table prevents application connectivity', 'cloud'],
  ['Plan a migration wave for legacy workloads', 'cloud'],
  ['The IAM role cannot assume the deployment role', 'cloud'],
  ['Kubernetes nodes cannot reach the container registry', 'cloud'],
  ['CloudFormation stack rollback needs investigation', 'cloud'],
  ['The landing zone needs another organizational unit', 'cloud'],
  ['Rotate the production infrastructure credentials', 'cloud'],
  ['Review the AWS network segmentation design', 'cloud'],
  ['Deployment failed after changing the load balancer', 'cloud'],
  ['The customer was charged twice for one card purchase', 'payments'],
  ['Yesterday settlement file is missing', 'payments'],
  ['A refund is still pending after seven days', 'payments'],
  ['Reconcile the merchant transaction batch', 'payments'],
  ['Update the billing tariff for this account', 'payments'],
  ['The payment gateway rejected an authorised card', 'payments'],
  ['Investigate interchange pricing on these transactions', 'payments'],
  ['The direct debit was collected for the wrong amount', 'payments'],
  ['Chargeback evidence must be submitted today', 'payments'],
  ['The acquiring ledger does not balance', 'payments'],
  ['Measure expected calibration error for the classifier', 'ai'],
  ['Vector search returns irrelevant documents', 'ai'],
  ['The embedding model produces unstable vectors', 'ai'],
  ['Evaluate abstention on out of scope requests', 'ai'],
  ['The agent selected the wrong tool', 'ai'],
  ['Compare inference latency across model variants', 'ai'],
  ['The training run did not beat the baseline', 'ai'],
  ['Inspect confidence scores for model drift', 'ai'],
  ['Build a retrieval augmented generation benchmark', 'ai'],
  ['The decision head needs cross fitted calibration', 'ai'],
].map(([text, label]) => ({ text, label }));

const heldOut = [
  ['AWS network policy is blocking a migrated service', 'cloud'],
  ['Create a landing zone for the new business unit', 'cloud'],
  ['A merchant refund has been duplicated', 'payments'],
  ['Reconcile card settlement totals', 'payments'],
  ['Benchmark the embedding model retrieval accuracy', 'ai'],
  ['The classifier confidence is poorly calibrated', 'ai'],
  ['Book a family camping holiday in France', 'other'],
  ['Suggest paint colours for the study wall', 'other'],
  ['What ingredients do I need for mushroom risotto?', 'other'],
];

async function score(engine, rows) {
  const items = [];
  const details = [];
  for (const [text, truth] of rows) {
    const started = performance.now();
    const result = await engine.decide(text, questions);
    const latencyMs = performance.now() - started;
    const answer = result.route;
    items.push({ predicted: answer.choice, truth, confidence: answer.confidence, abstain: answer.abstain, latencyMs });
    details.push({ text, truth, predicted: answer.choice, confidence: answer.confidence, abstain: answer.abstain, calibrated: answer.calibrated, head: answer.head });
  }
  return { metrics: evaluate(items), details };
}

const baseline = createTypesafe({
  warnOnHashEmbedder: false,
  engine: { choiceInstructions: true, abstainMode: 'sigmoid', catchAll: 'other', catchAllThreshold: 0.36 },
});
const before = await score(baseline, heldOut);

const trained = createTypesafe({
  warnOnHashEmbedder: false,
  engine: { choiceInstructions: true, crossfitCalibration: true, abstainMode: 'sigmoid', catchAll: 'other', catchAllThreshold: 0.36 },
});
// Compile the question before admitting labels so the trained head is attached
// to the same question definition used for evaluation.
await trained.decide(labelled[0].text, questions);
const trainReport = await trained.train('route', labelled, { kind: 'choice' });
const after = await score(trained, heldOut);

console.log(JSON.stringify({
  packageVersion: trained.version,
  backend: trained.backend,
  warning: 'The hash embedder is a wiring test double; semantic accuracy and calibration are not production evidence.',
  trainingExamples: labelled.length,
  heldOutExamples: heldOut.length,
  trainReport,
  before,
  after,
  stats: trained.stats(),
}, null, 2));
