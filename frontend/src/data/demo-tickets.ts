import type {
  Ticket,
  TicketChannel,
  TicketCategory,
  TicketPriority,
  TicketStatus,
  SupportTeam,
} from '@/types/ticket'
import { CATEGORY_TEAM } from '@/lib/ticket-config'
import { hoursFromNow, hoursAgo, daysAgo, seededRandom } from './time'

/**
 * Demonstration tickets (fixtures).
 *
 * Everything in this file is fictional sample data for the capstone demo.
 * It is deliberately kept out of UI components and services.
 */

const EMAIL_DOMAIN = 'myetmail.example'

function emailFor(name: string, suffix = ''): string {
  return `${name.split(' ')[0].toLowerCase()}.${name.split(' ')[1].toLowerCase()}${suffix}@${EMAIL_DOMAIN}`
}

/** Agent IDs that work each team (subset of the roster). */
const TEAM_AGENTS: Record<SupportTeam, string[]> = {
  customer_support: ['AG-01', 'AG-06', 'AG-07'],
  billing_team: ['AG-02'],
  logistics_team: ['AG-03'],
  technical_support: ['AG-04'],
  returns_team: ['AG-05'],
}

/* ------------------------------------------------------------------ */
/* Hand-written, detailed tickets (the most recent ~2 weeks)           */
/* ------------------------------------------------------------------ */

interface TicketSeed {
  id: string
  subject: string
  description: string
  requesterName: string
  channel: TicketChannel
  category: TicketCategory
  priority: TicketPriority
  status: TicketStatus
  assignedAgentId: string | null
  createdHoursAgo: number
  updatedHoursAgo: number
  reviewNote?: string
  suggestedCategory?: TicketCategory | null
  suggestedPriority?: TicketPriority | null
}

function makeTicket(seed: TicketSeed): Ticket {
  const team: SupportTeam = CATEGORY_TEAM[seed.category]
  const createdAt = hoursAgo(seed.createdHoursAgo)
  return {
    id: seed.id,
    subject: seed.subject,
    description: seed.description,
    requesterName: seed.requesterName,
    requesterEmail: emailFor(seed.requesterName),
    channel: seed.channel,
    category: seed.category,
    priority: seed.priority,
    status: seed.status,
    assignedTeam: team,
    assignedAgentId: seed.assignedAgentId,
    createdAt,
    updatedAt: hoursAgo(seed.updatedHoursAgo),
    // 8 working-hour SLA for active urgent/high tickets, none otherwise.
    dueAt:
      seed.status === 'resolved' || seed.status === 'closed'
        ? null
        : seed.priority === 'urgent' || seed.priority === 'high'
          ? hoursFromNow(8 - seed.updatedHoursAgo)
          : null,
    suggestedCategory:
      seed.suggestedCategory !== undefined ? seed.suggestedCategory : seed.category,
    suggestedPriority:
      seed.suggestedPriority !== undefined ? seed.suggestedPriority : seed.priority,
    reviewNote: seed.reviewNote ?? null,
  }
}

const HANDWRITTEN_SEEDS: TicketSeed[] = [
  {
    id: 'TF-1051',
    subject: 'Charged twice from Telebirr for order #ET-88412',
    description:
      'I paid for one order but two notifications of 1,450 birr from Telebirr came in within a minute. I need one payment reversed.',
    requesterName: 'Marta Alemu',
    channel: 'web_form',
    category: 'billing',
    priority: 'urgent',
    status: 'open',
    assignedAgentId: 'AG-02',
    createdHoursAgo: 1,
    updatedHoursAgo: 0.4,
  },
  {
    id: 'TF-1050',
    subject: 'Parcel #ETD-2214 stuck at Addis Ababa hub for 6 days',
    description:
      'Tracking says "arrived at hub" since last Monday. It was supposed to reach Bahir Dar this week for a birthday gift.',
    requesterName: 'Abel Tesfaye',
    channel: 'email',
    category: 'delivery',
    priority: 'urgent',
    status: 'new',
    assignedAgentId: null,
    createdHoursAgo: 2,
    updatedHoursAgo: 2,
  },
  {
    id: 'TF-1049',
    subject: 'Delivery notice for an order I do not recognise',
    description:
      'I received an SMS that my parcel from the Awassa market store is arriving tomorrow, but I have not placed any order this month.',
    requesterName: 'Genet Mulugeta',
    channel: 'phone',
    category: 'general',
    priority: 'high',
    status: 'needs_review',
    assignedAgentId: null,
    createdHoursAgo: 3,
    updatedHoursAgo: 2.6,
    suggestedCategory: null,
    suggestedPriority: null,
    reviewNote:
      'Could be a wrong-number SMS or account takeover. Classifier confidence 41% — needs human triage before routing.',
  },
  {
    id: 'TF-1048',
    subject: 'Checkout freezes after selecting Chapa as payment method',
    description:
      'On desktop Chrome the payment step spins forever after I pick Chapa. Same basket works on my phone, so it looks browser-related.',
    requesterName: 'Samuel Bekele',
    channel: 'web_form',
    category: 'technical',
    priority: 'high',
    status: 'open',
    assignedAgentId: 'AG-04',
    createdHoursAgo: 5,
    updatedHoursAgo: 1.2,
  },
  {
    id: 'TF-1047',
    subject: 'Exchange dress ordered for Meskel — size M to L',
    description:
      'The dress arrived with the tag still attached but the size runs small. I would like a straight exchange rather than a refund.',
    requesterName: 'Tigist Fikru',
    channel: 'web_form',
    category: 'returns',
    priority: 'normal',
    status: 'pending',
    assignedAgentId: 'AG-05',
    createdHoursAgo: 8,
    updatedHoursAgo: 3,
  },
  {
    id: 'TF-1046',
    subject: 'VAT line on invoice #INV-55103 does not match my subtotal',
    description:
      'My subtotal was 3,200 birr and the invoice shows VAT of 512 birr instead of 480. The difference is small but our finance team needs correct documents.',
    requesterName: 'Dagimawi Assefa',
    channel: 'email',
    category: 'billing',
    priority: 'high',
    status: 'new',
    assignedAgentId: null,
    createdHoursAgo: 9,
    updatedHoursAgo: 9,
  },
  {
    id: 'TF-1045',
    subject: 'Parcel going to the wrong address — Bahir Dar instead of Gondar',
    description:
      'I moved recently and the checkout still had my old address. The courier label shows Bahir Dar. Please correct it before dispatch.',
    requesterName: 'Hirut Wolde',
    channel: 'chat',
    category: 'delivery',
    priority: 'normal',
    status: 'open',
    assignedAgentId: 'AG-03',
    createdHoursAgo: 11,
    updatedHoursAgo: 6,
  },
  {
    id: 'TF-1044',
    subject: 'App logs me out constantly after update 4.12',
    description:
      'Since the Android update every session lasts about a minute. Cleared cache and reinstalled, still the same.',
    requesterName: 'Nahom Girma',
    channel: 'email',
    category: 'technical',
    priority: 'normal',
    status: 'resolved',
    assignedAgentId: 'AG-04',
    createdHoursAgo: 30,
    updatedHoursAgo: 14,
  },
  {
    id: 'TF-1043',
    subject: 'Do you deliver to Hawassa on Sundays?',
    description:
      'I want to send a cake box to my sister in Hawassa this Sunday. What are the weekend delivery options and fees?',
    requesterName: 'Betelhem Alemu',
    channel: 'chat',
    category: 'general',
    priority: 'low',
    status: 'open',
    assignedAgentId: null,
    createdHoursAgo: 14,
    updatedHoursAgo: 14,
  },
  {
    id: 'TF-1042',
    subject: 'Refund to Telebirr wallet not received after 10 days',
    description:
      'Ticket said refund was processed on the 8th but nothing has reached my wallet and my bank says they see nothing.',
    requesterName: 'Solomon Tsegaye',
    channel: 'web_form',
    category: 'billing',
    priority: 'normal',
    status: 'pending',
    assignedAgentId: 'AG-02',
    createdHoursAgo: 36,
    updatedHoursAgo: 20,
  },
  {
    id: 'TF-1041',
    subject: 'Perishable grocery order arrived completely thawed',
    description:
      'The frozen items in my grocery basket arrived at room temperature. The insulated liner was open. I have photos of the packaging.',
    requesterName: 'Amina Yusuf',
    channel: 'phone',
    category: 'delivery',
    priority: 'urgent',
    status: 'open',
    assignedAgentId: 'AG-03',
    createdHoursAgo: 40,
    updatedHoursAgo: 18,
  },
  {
    id: 'TF-1040',
    subject: 'Request pickup for return of cracked screen protector',
    description:
      'The tempered glass arrived already cracked. I repacked it with the order slip. Please schedule a courier pickup.',
    requesterName: 'Yared Bekele',
    channel: 'web_form',
    category: 'returns',
    priority: 'normal',
    status: 'new',
    assignedAgentId: null,
    createdHoursAgo: 44,
    updatedHoursAgo: 44,
  },
  {
    id: 'TF-1039',
    subject: 'Need detailed payment receipts for my expense report',
    description:
      'My company reimburses purchases. I need receipts with VAT breakdowns for orders from the last 30 days.',
    requesterName: 'Fikru Mengesha',
    channel: 'email',
    category: 'billing',
    priority: 'low',
    status: 'open',
    assignedAgentId: 'AG-02',
    createdHoursAgo: 52,
    updatedHoursAgo: 40,
  },
  {
    id: 'TF-1038',
    subject: 'Account shows a different person’s name after sign-in',
    description:
      'I signed in with my phone number and the account header shows another customer’s name and saved addresses. I am worried my number is linked to someone else’s profile.',
    requesterName: 'Kalkidan Bekele',
    channel: 'web_form',
    category: 'technical',
    priority: 'high',
    status: 'needs_review',
    assignedAgentId: null,
    createdHoursAgo: 56,
    updatedHoursAgo: 55,
    suggestedCategory: 'technical',
    suggestedPriority: 'urgent',
    reviewNote:
      'Possible account merge issue. Escalating for supervisor triage before any routing — do not reply to the customer yet.',
  },
  {
    id: 'TF-1037',
    subject: 'Courier demanded extra cash on delivery',
    description:
      'The rider asked for 300 birr on top of the label, which I had already paid online. I paid to avoid losing the parcel, but this needs checking.',
    requesterName: 'Zewditu Assefa',
    channel: 'phone',
    category: 'delivery',
    priority: 'high',
    status: 'pending',
    assignedAgentId: 'AG-03',
    createdHoursAgo: 70,
    updatedHoursAgo: 55,
  },
  {
    id: 'TF-1036',
    subject: 'Card declined but money left my Telebirr balance',
    description:
      'Checkout said payment failed twice, yet my wallet shows two 2,300 birr holds. One order is in my account, the other one vanished.',
    requesterName: 'Rahel Desta',
    channel: 'web_form',
    category: 'billing',
    priority: 'high',
    status: 'resolved',
    assignedAgentId: 'AG-02',
    createdHoursAgo: 96,
    updatedHoursAgo: 60,
  },
  {
    id: 'TF-1035',
    subject: 'Order status notifications duplicated on iPhone',
    description:
      'Every tracking push notification arrives twice with a few seconds gap. Phone restarted, notifications re-enabled, no change.',
    requesterName: 'Eyob Ayele',
    channel: 'email',
    category: 'technical',
    priority: 'normal',
    status: 'open',
    assignedAgentId: 'AG-04',
    createdHoursAgo: 120,
    updatedHoursAgo: 96,
  },
  {
    id: 'TF-1034',
    subject: 'Tracking shows delivered one day before parcel arrived',
    description:
      'The tracking page marked my order delivered last Tuesday, but courier the handed it over on Wednesday evening.',
    requesterName: 'Hiwot Tadesse',
    channel: 'chat',
    category: 'delivery',
    priority: 'normal',
    status: 'resolved',
    assignedAgentId: 'AG-03',
    createdHoursAgo: 150,
    updatedHoursAgo: 130,
  },
  {
    id: 'TF-1033',
    subject: 'How do promo codes combine with free shipping?',
    description:
      'I have a 10% code from the newsletter and a free-shipping offer. Can I use both on one basket?',
    requesterName: 'Mulugeta Gebre',
    channel: 'web_form',
    category: 'general',
    priority: 'low',
    status: 'closed',
    assignedAgentId: 'AG-06',
    createdHoursAgo: 170,
    updatedHoursAgo: 160,
  },
  {
    id: 'TF-1032',
    subject: 'Exchange hoodie for smaller size — tag still attached',
    description:
      'Size L is too loose, I would like S. Original packaging kept. Should I wait for pickup or drop it at the Piassa service point?',
    requesterName: 'Lemma Woldu',
    channel: 'web_form',
    category: 'returns',
    priority: 'low',
    status: 'pending',
    assignedAgentId: 'AG-05',
    createdHoursAgo: 190,
    updatedHoursAgo: 170,
  },
  {
    id: 'TF-1031',
    subject: 'Update phone number on my account',
    description:
      'I changed mobile providers. Old number still receives verification codes which worries me.',
    requesterName: 'Selamawit Negash',
    channel: 'chat',
    category: 'general',
    priority: 'normal',
    status: 'open',
    assignedAgentId: 'AG-07',
    createdHoursAgo: 210,
    updatedHoursAgo: 200,
  },
  {
    id: 'TF-1030',
    subject: 'Premium subscription charged twice this month',
    description:
      'My card was charged 99 birr twice for the same subscription period. Last month worked fine.',
    requesterName: 'Mekonnen Ayele',
    channel: 'email',
    category: 'billing',
    priority: 'urgent',
    status: 'resolved',
    assignedAgentId: 'AG-02',
    createdHoursAgo: 240,
    updatedHoursAgo: 210,
  },
  {
    id: 'TF-1029',
    subject: 'Box arrived crushed — kitchen glasses broken',
    description:
      'The outer box was torn and three glasses are in pieces. I sent photos through the app. Need replacement or refund.',
    requesterName: 'Tsion Habte',
    channel: 'web_form',
    category: 'delivery',
    priority: 'high',
    status: 'open',
    assignedAgentId: 'AG-03',
    createdHoursAgo: 260,
    updatedHoursAgo: 250,
  },
  {
    id: 'TF-1028',
    subject: 'Password reset email never arrives',
    description:
      'Requested a reset link five times over two days, checked spam. Nothing comes. My email is correct because order updates arrive.',
    requesterName: 'Biruk Alemayehu',
    channel: 'chat',
    category: 'technical',
    priority: 'normal',
    status: 'new',
    assignedAgentId: null,
    createdHoursAgo: 280,
    updatedHoursAgo: 280,
  },
]

export const HANDWRITTEN_TICKETS: Ticket[] = HANDWRITTEN_SEEDS.map(makeTicket)

/* ------------------------------------------------------------------ */
/* Older background tickets — generated deterministically              */
/* ------------------------------------------------------------------ */

interface OlderTemplate {
  subject: string
  description: string
  category: TicketCategory
  priority: TicketPriority
}

const OLDER_TEMPLATES: OlderTemplate[] = [
  {
    subject: 'Payment taken twice for one order',
    description: 'Bank statement shows two identical charge entries for a single checkout.',
    category: 'billing',
    priority: 'high',
  },
  {
    subject: 'Refund not reflected in Telebirr wallet',
    description: 'Return was approved and picked up, but the refund has not landed in the wallet.',
    category: 'billing',
    priority: 'normal',
  },
  {
    subject: 'Wrong VAT line on my invoice',
    description: 'The invoice round-up does not match the basket subtotal on the order email.',
    category: 'billing',
    priority: 'normal',
  },
  {
    subject: 'Question about payment gateway transaction fee',
    description: 'Is there any surcharge when paying with a commercial bank card?',
    category: 'billing',
    priority: 'low',
  },
  {
    subject: 'Parcel delayed beyond the estimated date',
    description: 'Estimated delivery passed four days ago and tracking has not moved.',
    category: 'delivery',
    priority: 'high',
  },
  {
    subject: 'Tracking number not updating',
    description: 'The tracking page has shown "label created" for several days.',
    category: 'delivery',
    priority: 'normal',
  },
  {
    subject: 'Old home address still on courier label',
    description: 'Checkout confirmation shows the previous address, need it corrected before dispatch.',
    category: 'delivery',
    priority: 'urgent',
  },
  {
    subject: 'Parcel delivered to the wrong compound',
    description: 'Neighbour received my parcel and refuses to open the gate in the evening.',
    category: 'delivery',
    priority: 'high',
  },
  {
    subject: 'App crashes when opening order history',
    description: 'Order history tab closes instantly on Android 13 after the latest update.',
    category: 'technical',
    priority: 'normal',
  },
  {
    subject: 'Cannot upload ID for account verification',
    description: 'Verification upload fails with "file too large" even for a 1 MB image.',
    category: 'technical',
    priority: 'high',
  },
  {
    subject: 'Password reset link expires instantly',
    description: 'Reset link says expired before I can open it, even when clicked immediately.',
    category: 'technical',
    priority: 'low',
  },
  {
    subject: 'Website images not loading on data connection',
    description: 'Product photos stay blank when not on Wi-Fi, even with full 4G signal.',
    category: 'technical',
    priority: 'low',
  },
  {
    subject: 'Return pickup never scheduled',
    description: 'Return was approved last week, but the courier pickup has not been booked.',
    category: 'returns',
    priority: 'high',
  },
  {
    subject: 'Refund after return still pending',
    description: 'Returned shoes were received at the warehouse eleven days ago, refund still pending.',
    category: 'returns',
    priority: 'normal',
  },
  {
    subject: 'Received the wrong size, need exchange',
    description: 'Ordered 42, received 40, box label matched the order slip.',
    category: 'returns',
    priority: 'normal',
  },
  {
    subject: 'Item arrived in an already-opened box',
    description: 'The box seal was cut and the manual is missing — looks like a used return.',
    category: 'returns',
    priority: 'low',
  },
  {
    subject: 'Do you deliver to Dire Dawa?',
    description: 'Planning a bulk stationery order, which delivery options cover Dire Dawa?',
    category: 'general',
    priority: 'low',
  },
  {
    subject: 'How do I use my gift card balance?',
    description: 'Received a gift card but cannot see how to apply it at checkout.',
    category: 'general',
    priority: 'low',
  },
  {
    subject: 'Question about seller warranty',
    description: 'Does the six-month warranty cover the listing from the third-party seller?',
    category: 'general',
    priority: 'normal',
  },
  {
    subject: 'Promo code not applying at checkout',
    description: 'Newsletter code is accepted but the basket total never changes.',
    category: 'general',
    priority: 'low',
  },
]

const REQUESTER_NAMES = [
  'Kebede Wolde',
  'Sara Mengistu',
  'Girmaw Fisseha',
  'Meseret Bekele',
  'Anthoniyos Tesfaye',
  'Hanna Yohannes',
  'Firaol Bonsa',
  'Lensa Bekalu',
  'Tagel Alemu',
  'Dawit Solomon',
  'Bezawit Yilma',
  'Nigussie Yanful',
  'Rahel Haile',
  'Kibrom Girmay',
  'Fanuye Robale',
  'Yoseph Wondimu',
  'Semira Aliyi',
  'Gashaw Ayele',
  'Mahder Tessema',
  'Mikal Tsegaye',
]

const R = seededRandom(20261019)

function pick<T>(list: T[]): T {
  return list[Math.floor(R() * list.length)]
}

/**
 * Older tickets (4–27 days ago) keep the dataset dense enough for the
 * 30-day trend charts. Statuses become more likely "resolved"/"closed"
 * with age, matching a support backlog realistically.
 */
function buildOlderTickets(): Ticket[] {
  const tickets: Ticket[] = []
  for (let i = 0; i < 56; i++) {
    const template = OLDER_TEMPLATES[i % OLDER_TEMPLATES.length]
    const ageDays = 4 + Math.floor(R() * 24) // 4 .. 27
    const createdAt = daysAgo(ageDays + R())

    // Status mix by age.
    const roll = R()
    let status: TicketStatus
    if (ageDays > 18) {
      status = roll < 0.62 ? 'resolved' : roll < 0.9 ? 'closed' : 'needs_review'
    } else if (ageDays > 9) {
      status =
        roll < 0.4
          ? 'resolved'
          : roll < 0.55
            ? 'closed'
            : roll < 0.75
              ? 'open'
              : roll < 0.92
                ? 'pending'
                : 'needs_review'
    } else {
      status =
        roll < 0.4
          ? 'open'
          : roll < 0.6
            ? 'pending'
            : roll < 0.75
              ? 'resolved'
              : roll < 0.87
                ? 'needs_review'
                : 'new'
    }

    const priorityRoll = R()
    const priority: TicketPriority =
      priorityRoll < 0.12
        ? 'high'
        : priorityRoll < 0.75
          ? template.priority
          : 'normal'

    const team: SupportTeam = CATEGORY_TEAM[template.category]
    const agents = TEAM_AGENTS[team]
    // New tickets stay unassigned; everything older was worked by an agent.
    const assignedAgentId =
      status === 'new' ? null : R() < 0.9 ? pick(agents) : null

    const reviewNote: string | null =
      status === 'needs_review'
        ? pick([
            'Classifier confidence below 60% — queued for human triage.',
            'Category ambiguity between billing and returns — needs a human decision.',
            'Duplicate report of an ongoing incident — confirm before routing.',
          ])
        : null

    tickets.push({
      id: `TF-2${String(400 + i)}`,
      subject: template.subject,
      description: template.description,
      requesterName: pick(REQUESTER_NAMES),
      requesterEmail: '',
      channel: pick<TicketChannel>(['web_form', 'email', 'phone', 'chat']),
      category: template.category,
      priority,
      status,
      assignedTeam: team,
      assignedAgentId,
      createdAt,
      updatedAt: createdAt,
      dueAt: null,
      suggestedCategory:
        status === 'needs_review' ? null : template.category,
      suggestedPriority: status === 'needs_review' ? null : priority,
      reviewNote,
    })
  }
  // Backfill requester emails now that names are fixed.
  for (const t of tickets) {
    t.requesterEmail = emailFor(t.requesterName)
  }
  return tickets
}

export const GENERATED_TICKETS: Ticket[] = buildOlderTickets()

/** Complete demonstration dataset, newest first. */
export const DEMO_TICKETS: Ticket[] = [...HANDWRITTEN_TICKETS, ...GENERATED_TICKETS].sort(
  (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
)

/** Quick lookup shared by the ticket detail placeholder and activity data. */
export const DEMO_TICKETS_BY_ID: ReadonlyMap<string, Ticket> = new Map(
  DEMO_TICKETS.map((ticket) => [ticket.id, ticket]),
)
