'use client';

import { useState, useEffect } from 'react';
import Navbar from '@/components/Navbar';

type TOSType = 'general' | 'exchange' | 'swap' | 'automm' | 'exchanger';

export default function TOSPage() {
  const [activeTab, setActiveTab] = useState<TOSType>('general');
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const tabs = [
    { id: 'general' as TOSType, name: 'Platform Terms' },
    { id: 'exchange' as TOSType, name: 'P2P Exchange' },
    { id: 'swap' as TOSType, name: 'Instant Swap' },
    { id: 'automm' as TOSType, name: 'AutoMM' },
    { id: 'exchanger' as TOSType, name: 'Exchanger Rules' }
  ];

  const getTOSContent = (type: TOSType) => {
    switch (type) {
      case 'general':
        return (
          <div className="tos-content">
            <section className="tos-section">
              <h2>1. Acceptance of Terms</h2>
              <p>
                By accessing or using Afroo Exchange ("the Platform," "we," "us," "our"), you acknowledge that you have read,
                understood, and agree to be bound by this Terms of Service Agreement ("Agreement"). If you do not agree, you
                must stop using the Platform immediately.
              </p>
            </section>

            <section className="tos-section">
              <h2>2. Nature of the Service</h2>
              <p>
                Afroo Exchange operates as a third-party mediator facilitating:
              </p>
              <ul>
                <li>Crypto-to-crypto swaps</li>
                <li>Fiat-to-crypto middleman exchanges</li>
                <li>Peer-to-peer transactions</li>
                <li>Escrow-based trading mechanisms</li>
                <li>Automated swaps via external APIs</li>
                <li>Discord-authenticated account access</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                <strong>Afroo Exchange is NOT:</strong>
              </p>
              <ul>
                <li>A bank or financial institution</li>
                <li>A custodian of user funds</li>
                <li>A money transmitter</li>
                <li>A regulated brokerage</li>
                <li>A financial advisor</li>
                <li>Responsible for validating the origin or subsequent use of user funds</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                All transactions occur between users, with Afroo Exchange acting only as a neutral intermediary to reduce scams,
                disputes, and fraudulent behavior.
              </p>
            </section>

            <section className="tos-section">
              <h2>3. Eligibility</h2>
              <p>To use the Platform, you confirm that you:</p>
              <ul>
                <li>Are at least 18 years old</li>
                <li>Have full legal capacity to enter binding contracts</li>
                <li>Are not restricted by sanctions or legal prohibitions</li>
                <li>Are compliant with all laws applicable to cryptocurrency usage in your jurisdiction</li>
                <li>Are acting on your own behalf, not as an agent for unlawful activity</li>
              </ul>
            </section>

            <section className="tos-section">
              <h2>4. Account Registration & Discord OAuth</h2>
              <p>
                The Platform uses Discord OAuth exclusively for authentication. By logging in, you agree:
              </p>
              <ul>
                <li>To follow Discord's Terms of Service, Community Guidelines, and API policies</li>
                <li>That your Discord account ID, tag, avatar, and permission scopes may be used for authentication and security</li>
                <li>That we may revoke access at our discretion</li>
                <li>That maintaining the security of your Discord account is your sole responsibility</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                We do not store Discord passwords, tokens, or privileged authentication data.
              </p>
            </section>

            <section className="tos-section">
              <h2>5. Data Privacy</h2>
              <p>We collect only the data required to operate the service, including:</p>
              <ul>
                <li>Discord ID and account metadata</li>
                <li>Transaction logs</li>
                <li>Messages submitted through escrow or dispute systems</li>
                <li>Wallet addresses, transaction hashes, and swap history</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>We do not:</p>
              <ul>
                <li>Sell user data</li>
                <li>Share PII except when legally required or in the event of bank/payment disputes</li>
                <li>Collect unnecessary personal information</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                We may disclose transaction logs, chat transcripts, timestamps, wallet hashes, and identity-linked data when
                necessary to defend a chargeback dispute, fraud investigation, or legal threat.
              </p>
            </section>

            <section className="tos-section">
              <h2>6. Prohibited Conduct</h2>
              <p>You agree NOT to engage in any of the following:</p>

              <p style={{ marginTop: '1rem' }}><strong>6.1 Illegal Financial Use</strong></p>
              <ul>
                <li>Money laundering</li>
                <li>Use of stolen or illicit funds</li>
                <li>Fraudulent transactions</li>
                <li>Tax evasion attempts</li>
                <li>Circumvention of sanctions</li>
              </ul>

              <p style={{ marginTop: '1rem' }}><strong>6.2 Platform Abuse</strong></p>
              <ul>
                <li>Chargebacks or false payment disputes</li>
                <li>Attempted scams or manipulation</li>
                <li>Multi-accounting to evade restrictions</li>
                <li>Threats, harassment, blackmail, or doxing</li>
                <li>Using transaction details or personal data to harm others</li>
                <li>Disrupting platform operations (DDoS, exploits, API abuse)</li>
                <li>Attempting legal intimidation or frivolous legal actions</li>
              </ul>

              <p style={{ marginTop: '1rem' }}><strong>6.3 Technical Misuse</strong></p>
              <ul>
                <li>Unauthorized automation</li>
                <li>Scraping data</li>
                <li>Injecting malware or malicious scripts</li>
                <li>Interfering with crypto swap APIs</li>
                <li>Attempting to reverse engineer or tamper with platform systems</li>
              </ul>

              <p style={{ marginTop: '1rem' }}>
                Violation of any prohibited activity will result in immediate account termination, loss of all funds held in
                escrow, and permanent ban.
              </p>
            </section>

            <section className="tos-section">
              <h2>7. Middleman Services & Escrow</h2>
              <p>Afroo Exchange offers middleman and escrow services to help prevent scams. However:</p>
              <ul>
                <li>All transactions are at your own risk</li>
                <li>You are solely responsible for verifying counterparties</li>
                <li>We do not guarantee transaction success or completion</li>
                <li>We are not liable for miscommunication, delays, or user negligence</li>
                <li>We do not insure losses caused by exchangers, buyers, or sellers</li>
              </ul>
            </section>

            <section className="tos-section">
              <h2>8. Third-Party APIs & Providers</h2>
              <p>The Platform integrates with external tools such as:</p>
              <ul>
                <li>Crypto networks</li>
                <li>Swap routing engines</li>
                <li>Fiat on-ramps/off-ramps</li>
                <li>Blockchain explorers</li>
                <li>Payment processors</li>
                <li>Discord API</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>By using the Platform, you acknowledge:</p>
              <ul>
                <li>We do not control third-party services</li>
                <li>We are not liable for downtime, delays, failures, incorrect routing, or lost funds caused by these services</li>
                <li>Any dispute involving a third party is outside our responsibility</li>
              </ul>
            </section>

            <section className="tos-section">
              <h2>9. Financial Disclaimer & Loss of Funds</h2>
              <p>You agree that Afroo Exchange is NOT LIABLE for any loss of funds due to:</p>
              <ul>
                <li>User error</li>
                <li>Sending to wrong wallet addresses</li>
                <li>Blockchain congestion</li>
                <li>Network delays or failed confirmations</li>
                <li>External wallet shutdowns</li>
                <li>Exchanger misconduct</li>
                <li>Fraud from users</li>
                <li>Payment processor reversals</li>
                <li>Chargebacks</li>
                <li>Lost private keys</li>
                <li>Bank holds, freezes, or investigations</li>
                <li>Incorrect prices, slippage, or swap results</li>
                <li>Liquidity shortages</li>
                <li>Volatility, market drops, or price crashes</li>
                <li>Any other financial loss of any kind</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                All cryptocurrency transactions are final, irreversible, and at your own risk.
              </p>
            </section>

            <section className="tos-section">
              <h2>10. Dispute Resolution</h2>
              <p><strong>10.1 Internal Resolution</strong></p>
              <p>
                All disputes must be handled through Afroo Exchange support. Resolution will be determined solely at the
                discretion of the administration, and their decision is final.
              </p>

              <p style={{ marginTop: '1rem' }}><strong>10.2 Use of Transcripts & Logs</strong></p>
              <p>You agree that:</p>
              <ul>
                <li>All transaction details</li>
                <li>Submitted evidence</li>
                <li>Messages and timestamps</li>
                <li>Wallet hashes and records</li>
                <li>API logs</li>
              </ul>
              <p>may be used as evidence to resolve disputes internally or defend against external disputes.</p>

              <p style={{ marginTop: '1rem' }}><strong>10.3 Chargebacks / False Disputes</strong></p>
              <p>Charging back or opening a false dispute with your bank, PayPal, card issuer, crypto payment processor, or any
              third-party platform will result in:</p>
              <ul>
                <li>Immediate permanent ban</li>
                <li>Forfeiture of all funds</li>
                <li>Full submission of logs and evidence to the payment provider</li>
                <li>Legal reporting if necessary</li>
              </ul>
            </section>

            <section className="tos-section">
              <h2>11. Liability & Warranty Disclaimer</h2>
              <p>To the maximum extent allowed by law:</p>
              <ul>
                <li>The Platform is provided "as-is" and without warranty</li>
                <li>We are NOT responsible for lost profits, damages, or financial losses</li>
                <li>We do NOT guarantee uptime, accuracy, or uninterrupted service</li>
                <li>We do NOT provide financial, legal, or investment advice</li>
                <li>You use the Platform at your own risk</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                Our total liability under any circumstance shall never exceed $0.00.
              </p>
            </section>

            <section className="tos-section">
              <h2>12. Indemnification</h2>
              <p>You agree to indemnify and hold Afroo Exchange harmless from:</p>
              <ul>
                <li>Disputes involving other users</li>
                <li>Disputes involving banks, processors, or platforms</li>
                <li>Loss of funds</li>
                <li>Your actions or negligence</li>
                <li>Violations of these Terms</li>
                <li>Attempts to misuse or harm the Platform</li>
              </ul>
            </section>

            <section className="tos-section">
              <h2>13. Service Protection & Legal Restrictions</h2>
              <p>You agree NOT to:</p>
              <ul>
                <li>File fraudulent legal threats</li>
                <li>Attempt extortion or leverage law enforcement maliciously</li>
                <li>Harm our service via DDoS, freezing, scraping, or exploitation</li>
                <li>Engage in blackmail regarding transactions or PII</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                Attempting any of the above results in immediate and permanent termination.
              </p>
            </section>

            <section className="tos-section">
              <h2>14. Modifications to Terms</h2>
              <p>
                We may modify these Terms at any time. Updates will be announced through Discord or the Platform. Continued use
                constitutes acceptance of the updated Terms.
              </p>
            </section>

            <section className="tos-section">
              <h2>15. Governing Law & Arbitration</h2>
              <ul>
                <li>This Agreement is governed by the laws of the United States</li>
                <li>All disputes shall be resolved through binding arbitration</li>
                <li>Class action lawsuits and collective legal actions are waived</li>
                <li>Users agree not to pursue claims outside of arbitration</li>
              </ul>
            </section>

            <section className="tos-section">
              <h2>16. Contact</h2>
              <p>For questions or disputes, contact support through:</p>
              <ul>
                <li>Platform ticket system</li>
                <li>Discord support team</li>
              </ul>
            </section>
          </div>
        );

      case 'exchange':
        return (
          <div className="tos-content">
            <div style={{ marginBottom: '2rem', padding: '1rem', background: 'rgba(168, 131, 255, 0.1)', borderRadius: '0.5rem', border: '1px solid rgba(168, 131, 255, 0.3)' }}>
              <p style={{ margin: 0 }}>
                These P2P Exchange Terms apply to all users accessing or participating in Afroo's Peer-to-Peer Exchange System.
                By creating a trade, opening a P2P ticket, or engaging with exchangers, you agree to: <strong>the General Terms of Service,
                AND this P2P-specific Terms of Service, AND any Additional Ticket-Level TOS posted inside your trade ticket by Afroo staff
                or the assigned exchanger.</strong>
              </p>
            </div>

            <section className="tos-section">
              <h2>1. Description of P2P Exchange Services</h2>
              <p>Afroo provides a P2P marketplace and escrow system where users perform:</p>
              <ul>
                <li>Fiat → Crypto trades</li>
                <li>Crypto → Fiat trades</li>
                <li>Crypto → Crypto swaps</li>
                <li>Fiat → Fiat payments or transfers</li>
                <li>Balance payments or card/bank transactions</li>
                <li>Middleman services for digital goods or asset exchanges</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                <strong>Afroo is not a party to any trade.</strong> Afroo:
              </p>
              <ul>
                <li>Does not handle fiat payments</li>
                <li>Does not verify payment authenticity</li>
                <li>Does not guarantee counterparties</li>
                <li>Only provides ticket management, logging, and escrow handling</li>
              </ul>
            </section>

            <section className="tos-section">
              <h2>2. Escrow System</h2>
              <p>All P2P trades utilize Afroo's secure escrow to temporarily hold cryptocurrency until:</p>
              <ul>
                <li>Payment is confirmed by the seller</li>
                <li>Ticket TOS requirements are met</li>
                <li>Admin or exchanger approves release</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                Afroo escrow protects the exchange process but does not insure funds.
              </p>
            </section>

            <section className="tos-section">
              <h2>3. Acceptance of Ticket-Level TOS</h2>
              <p>By opening a P2P ticket, you automatically agree to:</p>
              <ul>
                <li>All rules posted in that ticket</li>
                <li>All instructions from Afroo staff</li>
                <li>All exchanger requirements</li>
                <li>Any additional conditions imposed during the trade</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                <strong>Failure to follow ticket-specific instructions forfeits all funds held in escrow.</strong>
              </p>
            </section>

            <section className="tos-section">
              <h2>4. Payment Methods & Buyer Responsibilities</h2>
              <p>Allowed methods include, but are not limited to:</p>
              <ul>
                <li>Bank transfers</li>
                <li>Debit or credit card payments</li>
                <li>Zelle / Cash App / PayPal / Venmo / Revolut</li>
                <li>Wire transfers</li>
                <li>E-transfers</li>
                <li>Other mutually agreed third-party platforms</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>The buyer is responsible for:</p>
              <ul>
                <li>Sending the correct amount</li>
                <li>Ensuring payment is legitimate, non-reversible, and confirmed</li>
                <li>Providing accurate evidence</li>
                <li>Not using stolen cards, unauthorized accounts, or fraudulent banking</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                Afroo does not verify, validate, or process fiat payments in any way.
              </p>
            </section>

            <section className="tos-section">
              <h2>5. Chargebacks & Reversals – ZERO TOLERANCE</h2>
              <p>Opening a chargeback, reversal, dispute, or fraud report with your bank, payment provider, card issuer, PayPal,
              Zelle, CashApp, or any other platform will result in:</p>
              <ul>
                <li>Immediate permanent ban</li>
                <li>Automatic forfeiture of ALL funds in Afroo escrow</li>
                <li>Release of all evidence (transaction logs, timestamps, chats, wallet hashes, screenshots, recordings) to the payment institution</li>
                <li>A dispute response filed in Afroo's favor</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                <strong>This applies even if the chargeback is filed after the trade concludes.</strong>
              </p>
            </section>

            <section className="tos-section">
              <h2>6. Forfeiture Rules</h2>
              <p><strong>6.1 Bank/Card Trades</strong></p>
              <p>If you create a ticket to pay with card or bank, you acknowledge:</p>
              <ul>
                <li>You forfeit all rights to reverse or dispute</li>
                <li>You accept all liability</li>
                <li>You fully authorize the transaction</li>
                <li>All funds are permanently forfeited to Afroo if ANY dispute is initiated</li>
              </ul>

              <p style={{ marginTop: '1rem' }}><strong>6.2 Ticket Disputes</strong></p>
              <p>If you attempt to scam, provide false evidence, refuse to follow instructions, delay the trade, try to reverse
              the payment, or abuse the system, Afroo may immediately seize escrow funds and award them to the counterparty or
              retain them as penalty.</p>

              <p style={{ marginTop: '1rem' }}><strong>6.3 Non-Compliance</strong></p>
              <p>Failure to comply with ANY part of the P2P Terms or ticket TOS results in:</p>
              <ul>
                <li>Permanent ban</li>
                <li>Loss of reputation</li>
                <li>Forfeiture of funds</li>
              </ul>
            </section>

            <section className="tos-section">
              <h2>7. Lost Funds, Errors, and Irreversible Transactions</h2>
              <p>Afroo is NOT responsible for lost funds due to:</p>
              <ul>
                <li>Sending crypto to the wrong wallet</li>
                <li>Reversible fiat transfers</li>
                <li>Fraudulent payment methods</li>
                <li>Bank reversals</li>
                <li>User mistakes</li>
                <li>Incorrect wallet networks</li>
                <li>Transaction delays</li>
                <li>Blockchain congestion or failures</li>
                <li>External API downtime</li>
                <li>Liquidity fluctuations</li>
                <li>Inaccurate payment verification</li>
                <li>Exchanger errors</li>
                <li>Client misunderstanding</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                <strong>Once crypto is released from escrow, the transaction is final and irreversible.</strong>
              </p>
            </section>

            <section className="tos-section">
              <h2>8. Dispute Resolution (Admin Has Final Say)</h2>
              <p>All disputes must occur inside the Afroo ticket. Evidence accepted includes:</p>
              <ul>
                <li>Screenshots</li>
                <li>Bank transaction logs</li>
                <li>Wallet hashes</li>
                <li>Chat transcripts</li>
                <li>API confirmations</li>
                <li>Video proof</li>
                <li>Staff observations</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>Afroo Admins resolve disputes. Their decision:</p>
              <ul>
                <li>Is final</li>
                <li>Cannot be appealed</li>
                <li>Cannot be challenged externally</li>
                <li>Cannot be reversed</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                Attempts to dispute Afroo's decision result in: account termination, evidence submission to third parties, and fund forfeiture.
              </p>
            </section>

            <section className="tos-section">
              <h2>9. Third-Party Services & External APIs</h2>
              <p>The P2P Exchange relies on:</p>
              <ul>
                <li>Blockchain networks</li>
                <li>Third-party API swap providers</li>
                <li>Payment providers</li>
                <li>Wallet systems</li>
                <li>Discord authentication</li>
                <li>Third-party infrastructure</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>Afroo has:</p>
              <ul>
                <li>No control over these services</li>
                <li>No responsibility for failures, delays, reversals, downtime, or incorrect data</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                Any losses due to external providers are not Afroo's responsibility.
              </p>
            </section>

            <section className="tos-section">
              <h2>10. Responsibilities of Sellers / Exchangers</h2>
              <p>All Afroo-authorized exchangers agree to:</p>
              <ul>
                <li>Follow ticket rules</li>
                <li>Respond within reasonable time</li>
                <li>Use escrow properly</li>
                <li>Never accept reversible payments unless ticket TOS permits</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                Sellers hold full responsibility for fiat verification. Afroo does not mediate bank or card verification.
              </p>
            </section>

            <section className="tos-section">
              <h2>11. Responsibilities of Buyers</h2>
              <p>Buyers must:</p>
              <ul>
                <li>Pay the exact amount</li>
                <li>Use legitimate verified accounts</li>
                <li>Avoid reversible or suspicious payments</li>
                <li>Follow ticket instructions</li>
                <li>Submit correct proof</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                Failure to do so results in refusal of release and possible forfeiture.
              </p>
            </section>

            <section className="tos-section">
              <h2>12. Reputation System</h2>
              <p>Your reputation affects:</p>
              <ul>
                <li>Access to exchangers</li>
                <li>Trade limits</li>
                <li>Speed of escrow release</li>
                <li>Eligibility for sensitive transactions</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                Fake reviews, manipulation, or retaliation will result in reputation resets or bans.
              </p>
            </section>

            <section className="tos-section">
              <h2>13. Cancellation Policy</h2>
              <p>Trades may be cancelled:</p>
              <ul>
                <li>Before escrow is funded, without penalty</li>
                <li>After escrow is funded, cancellation may penalize your reputation</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                Repeated cancellations result in temporary or permanent restrictions.
              </p>
            </section>

            <section className="tos-section">
              <h2>14. Misuse, Harassment, Doxing, Blackmail</h2>
              <p>Using ANY information obtained from a P2P trade to harass, blackmail, dox, threaten, scam, or intimidate results in:</p>
              <ul>
                <li>Immediate permanent ban</li>
                <li>Forfeiture of all funds</li>
                <li>Reporting to relevant authorities</li>
              </ul>
            </section>

            <section className="tos-section">
              <h2>15. No Financial, Legal, or Tax Advice</h2>
              <p>Afroo does NOT:</p>
              <ul>
                <li>Provide investment guidance</li>
                <li>Guarantee profits</li>
                <li>Advise on tax obligations</li>
                <li>Certify transaction legality</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                All trades are performed at your own risk and responsibility.
              </p>
            </section>

            <section className="tos-section">
              <h2>16. Liability Limitation</h2>
              <p>To the maximum extent permitted by law:</p>
              <ul>
                <li>Afroo bears zero liability for any losses</li>
                <li>Afroo provides the service as-is</li>
                <li>Afroo is not responsible for counterparties, banks, payment processors, or blockchain failures</li>
                <li>Afroo's total liability is $0.00</li>
              </ul>
            </section>

            <section className="tos-section">
              <h2>17. Indemnification</h2>
              <p>You agree to indemnify Afroo against:</p>
              <ul>
                <li>Claims from banks or financial institutions</li>
                <li>Payment disputes</li>
                <li>Chargebacks</li>
                <li>Lost funds</li>
                <li>Fraud investigations</li>
                <li>Misuse of the P2P service</li>
                <li>Violations of ticket TOS</li>
                <li>Damages caused by your negligence or actions</li>
              </ul>
            </section>

            <section className="tos-section">
              <h2>18. Enforcement & Modification</h2>
              <p>Afroo reserves the right to:</p>
              <ul>
                <li>Modify these Terms at any time</li>
                <li>Suspend or ban users at its discretion</li>
                <li>Alter fees</li>
                <li>Change ticket requirements</li>
                <li>Update compliance rules</li>
                <li>Enforce penalties and forfeiture</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                Continued use means continued acceptance.
              </p>
            </section>
          </div>
        );

      case 'swap':
        return (
          <div className="tos-content">
            <div style={{ marginBottom: '2rem', padding: '1rem', background: 'rgba(168, 131, 255, 0.1)', borderRadius: '0.5rem', border: '1px solid rgba(168, 131, 255, 0.3)' }}>
              <p style={{ margin: 0 }}>
                These Crypto-to-Crypto Swap Terms apply to all users accessing or using Afroo's automated cryptocurrency swap system.
                By initiating a swap, you agree to: <strong>Afroo General Terms of Service, AND these Swap Terms, AND ChangeNOW's Terms
                of Use available at <a href="https://changenow.io/terms-of-use" target="_blank" rel="noopener noreferrer" style={{ color: '#a883ff', textDecoration: 'underline' }}>https://changenow.io/terms-of-use</a></strong>
              </p>
            </div>

            <section className="tos-section">
              <h2>1. Service Description</h2>
              <p>
                Afroo Swap enables users to perform automated crypto-to-crypto conversions through the ChangeNOW API, which executes
                all transactions, liquidity routing, rate calculations, and blockchain interactions.
              </p>
              <p style={{ marginTop: '1rem' }}>Afroo does not:</p>
              <ul>
                <li>Custody your funds</li>
                <li>Execute swaps directly</li>
                <li>Control liquidity</li>
                <li>Guarantee rates</li>
                <li>Determine compliance rules for ChangeNOW</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                Afroo solely provides the interface facilitating communication with ChangeNOW.
              </p>
            </section>

            <section className="tos-section">
              <h2>2. Acceptance of Third-Party Terms (ChangeNOW Binding Agreement)</h2>
              <p>By using Afroo Swap, you explicitly agree to:</p>
              <ul>
                <li>ChangeNOW's Terms of Use</li>
                <li>All policies, rules, limits, and restrictions imposed by ChangeNOW</li>
                <li>Any AML/KYC/Compliance requirements ChangeNOW requests</li>
                <li>ChangeNOW's refund, cancellation, or denial decisions</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                Afroo is not responsible for ChangeNOW's actions, decisions, or restrictions.
              </p>
            </section>

            <section className="tos-section">
              <h2>3. User Responsibility for Funds</h2>
              <p>You agree that YOU are fully and solely responsible for:</p>
              <ul>
                <li>The legality and source of your funds</li>
                <li>The legality and purpose of your swapped funds</li>
                <li>Any tax or reporting obligations</li>
                <li>Compliance with your local laws</li>
                <li>Ensuring the swap is lawful in your jurisdiction</li>
                <li>Ensuring the funds are not illicit or sanctioned</li>
                <li>Ensuring you own the wallets involved</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>Afroo and ChangeNOW do not validate, verify, or guarantee:</p>
              <ul>
                <li>Ownership of funds</li>
                <li>Legitimacy of funds</li>
                <li>Legality of intended usage</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                <strong>You assume 100% liability for all financial, legal, and regulatory consequences of your swap.</strong>
              </p>
            </section>

            <section className="tos-section">
              <h2>4. No Liability for Lost Funds</h2>
              <p>Afroo is not liable, under any circumstances, for lost funds caused by:</p>
              <ul>
                <li>Incorrect or invalid wallet addresses</li>
                <li>Blockchain congestion</li>
                <li>Network delays or failures</li>
                <li>Insufficient liquidity</li>
                <li>Incorrect chain selection</li>
                <li>Smart contract errors</li>
                <li>Rate changes</li>
                <li>ChangeNOW errors</li>
                <li>ChangeNOW downtime</li>
                <li>Wrong network selection (e.g., sending ETH to BEP20)</li>
                <li>User mistakes</li>
                <li>Failed swaps</li>
                <li>Assets sent but not received</li>
                <li>Stuck or unconfirmed transactions</li>
                <li>Frozen or seized funds by ChangeNOW</li>
                <li>Third-party wallet failures</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                <strong>All transactions are final and AT YOUR OWN RISK.</strong>
              </p>
            </section>

            <section className="tos-section">
              <h2>5. Swap Process</h2>
              <p>You acknowledge that swaps operate as follows:</p>
              <ul>
                <li>User selects source & destination currencies</li>
                <li>User provides a valid destination wallet address</li>
                <li>Afroo sends request parameters to ChangeNOW</li>
                <li>ChangeNOW provides estimated rates</li>
                <li>User approves the swap</li>
                <li>User sends crypto to the address generated by ChangeNOW</li>
                <li>ChangeNOW performs the conversion</li>
                <li>ChangeNOW sends the converted funds to the destination address</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                <strong>Afroo does not touch, control, or process your crypto at any point.</strong>
              </p>
            </section>

            <section className="tos-section">
              <h2>6. Exchange Rates & Slippage</h2>
              <p>You agree that:</p>
              <ul>
                <li>Rates are estimates, not guarantees</li>
                <li>Rates may change before or during the swap</li>
                <li>Final received amount may be higher or lower than expected</li>
                <li>Market volatility affects swap results</li>
                <li>Afroo is not responsible for rate inaccuracies</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                If ChangeNOW adjusts or modifies rates due to slippage, you accept those results.
              </p>
            </section>

            <section className="tos-section">
              <h2>7. Fees & Network Costs</h2>
              <p>Displayed fees may include:</p>
              <ul>
                <li>ChangeNOW fees</li>
                <li>Miner or network fees</li>
                <li>Afroo service fees</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>All fees are shown before confirmation. By approving the swap, you accept:</p>
              <ul>
                <li>All costs</li>
                <li>All variable network fees</li>
                <li>Possible repeat network fees for retries</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                <strong>Fees are non-refundable.</strong>
              </p>
            </section>

            <section className="tos-section">
              <h2>8. Wallet Responsibility</h2>
              <p>You are solely responsible for:</p>
              <ul>
                <li>Providing a correct wallet address</li>
                <li>Using the correct network</li>
                <li>Ensuring you control the address</li>
                <li>Ensuring wallet compatibility</li>
                <li>Verifying chain-specific details (e.g., tags, memos, destination codes)</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                <strong>Funds sent to the wrong address cannot be recovered.</strong> Afroo and ChangeNOW are not responsible for
                misdirected or lost coins.
              </p>
            </section>

            <section className="tos-section">
              <h2>9. Processing Times</h2>
              <p>Swap times vary based on:</p>
              <ul>
                <li>Blockchain activity</li>
                <li>Asset type</li>
                <li>Network congestion</li>
                <li>Liquidity availability</li>
                <li>ChangeNOW processing queues</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                Delays do not entitle you to compensation, refunds, or reversals.
              </p>
            </section>

            <section className="tos-section">
              <h2>10. Failed Transactions</h2>
              <p>Failed transactions are handled exclusively by ChangeNOW, not Afroo. Possible outcomes include:</p>
              <ul>
                <li>Refund to sending address</li>
                <li>Refund minus network fees</li>
                <li>Partial refund</li>
                <li>Swap retry</li>
                <li>Swap cancellation by ChangeNOW</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                Afroo has zero control over refund outcomes. If a refund is delayed or not received, you must contact ChangeNOW, not Afroo.
              </p>
            </section>

            <section className="tos-section">
              <h2>11. Transaction Limits</h2>
              <p>Minimum and maximum swap amounts are controlled by ChangeNOW and may:</p>
              <ul>
                <li>Update at any time</li>
                <li>Vary by asset pair</li>
                <li>Change due to liquidity conditions</li>
                <li>Be determined algorithmically</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>If your transaction is below or above limits, ChangeNOW may:</p>
              <ul>
                <li>Reject the transaction</li>
                <li>Return the funds</li>
                <li>Retain certain fees</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                Afroo has no involvement in these decisions.
              </p>
            </section>

            <section className="tos-section">
              <h2>12. Compliance, AML, and High-Risk Behavior</h2>
              <p>You agree that ChangeNOW may:</p>
              <ul>
                <li>Freeze transactions</li>
                <li>Reject swaps</li>
                <li>Request KYC</li>
                <li>Flag suspicious behavior</li>
                <li>Report your activity to authorities</li>
                <li>Retain funds in compliance cases</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                Afroo is not responsible for compliance actions taken by ChangeNOW.
              </p>
            </section>

            <section className="tos-section">
              <h2>13. No Reversals / Finality</h2>
              <p>Once funds are sent for a swap:</p>
              <ul>
                <li>The transaction is final</li>
                <li>It cannot be reversed</li>
                <li>Afroo cannot cancel or modify your swap</li>
                <li>ChangeNOW has full control over outcomes</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                <strong>Crypto transactions cannot be undone.</strong>
              </p>
            </section>

            <section className="tos-section">
              <h2>14. No Warranties & No Guarantees</h2>
              <p>Afroo provides this service AS-IS, without:</p>
              <ul>
                <li>Warranty</li>
                <li>Guarantees</li>
                <li>Promises</li>
                <li>Refund guarantees</li>
                <li>Compensation</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                You accept full personal and financial risk when using the swap service.
              </p>
            </section>

            <section className="tos-section">
              <h2>15. Indemnification</h2>
              <p>You agree to indemnify Afroo against all claims arising from:</p>
              <ul>
                <li>Source of your funds</li>
                <li>Use of your funds</li>
                <li>Illegal transactions</li>
                <li>AML/KYC violations</li>
                <li>Losses caused by errors</li>
                <li>Losses caused by external services</li>
                <li>Disputes with ChangeNOW</li>
                <li>Blockchain issues</li>
                <li>Your non-compliance</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                <strong>Afroo will not be held liable under any circumstances.</strong>
              </p>
            </section>

            <section className="tos-section">
              <h2>16. Modification & Enforcement</h2>
              <p>Afroo may modify these Terms at any time. Continued use constitutes acceptance.</p>
              <p style={{ marginTop: '1rem' }}>Afroo reserves the right to:</p>
              <ul>
                <li>Suspend access</li>
                <li>Limit swap functionality</li>
                <li>Block suspicious users</li>
                <li>Report unlawful activity</li>
                <li>Enforce any penalty necessary to protect the platform</li>
              </ul>
            </section>
          </div>
        );

      case 'automm':
        return (
          <div className="tos-content">
            <div style={{ marginBottom: '2rem', padding: '1rem', background: 'rgba(168, 131, 255, 0.1)', borderRadius: '0.5rem', border: '1px solid rgba(168, 131, 255, 0.3)' }}>
              <p style={{ margin: 0 }}>
                These Auto Middle Man Terms govern your use of Afroo's automated escrow-protected middleman system provided through
                the Afroo Bot and Afroo Services. By using AutoMM, you agree to: <strong>the Afroo General Terms of Service, AND any
                applicable P2P Terms, AND these AutoMM Terms, AND any ticket-level TOS provided during a transaction.</strong>
              </p>
            </div>

            <section className="tos-section">
              <h2>1. Service Description</h2>
              <p>
                AutoMM is a free automated escrow system provided by Afroo to help members safely exchange digital goods, currencies,
                services, or assets.
              </p>
              <p style={{ marginTop: '1rem' }}>AutoMM:</p>
              <ul>
                <li>Only holds crypto, digital assets, or items temporarily in escrow</li>
                <li>Does NOT judge fairness, quality, or legitimacy of trades</li>
                <li>Does NOT guarantee outcomes</li>
                <li>Does NOT act as a marketplace, broker, or financial institution</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                <strong>AutoMM exists solely to reduce scams between users, not to guarantee trade success.</strong>
              </p>
            </section>

            <section className="tos-section">
              <h2>2. No Liability for Funds, Items, or Trade Outcomes</h2>
              <p>Afroo and AutoMM are NOT responsible for:</p>
              <ul>
                <li>Lost funds</li>
                <li>Lost items</li>
                <li>Damaged goods</li>
                <li>Missing deliveries</li>
                <li>Digital items not received</li>
                <li>Faulty products</li>
                <li>Scams caused by users</li>
                <li>Disputes over item quality, accuracy, or value</li>
                <li>Delays or cancellations</li>
                <li>Any issues between the two trading parties</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>Afroo does not insure:</p>
              <ul>
                <li>Crypto</li>
                <li>Digital assets</li>
                <li>Virtual items</li>
                <li>Codes or keys</li>
                <li>Accounts</li>
                <li>In-game items</li>
                <li>NFT transfers</li>
                <li>Any other traded property</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                <strong>Users trade at their own risk.</strong>
              </p>
            </section>

            <section className="tos-section">
              <h2>3. Escrow Handling</h2>
              <p>AutoMM escrow only holds funds or items temporarily until:</p>
              <ul>
                <li>Both parties acknowledge that conditions are met, OR</li>
                <li>Admin intervenes and makes a final decision (if necessary)</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>During escrow:</p>
              <ul>
                <li>Afroo does NOT guarantee the safety of funds outside the system</li>
                <li>Afroo does NOT validate item legitimacy</li>
                <li>Afroo does NOT confirm quality or authenticity</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                Escrow exists only to prevent direct scams, not to guarantee final trade satisfaction.
              </p>
            </section>

            <section className="tos-section">
              <h2>4. Attempting to Bypass AutoMM</h2>
              <p>Attempting to bypass AutoMM:</p>
              <ul>
                <li>Trading outside of escrow</li>
                <li>Trading partially outside the system</li>
                <li>Attempting to move to DMs</li>
                <li>Attempting to trick the bot</li>
                <li>Using fake screenshots or fabricated proof</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>Will result in:</p>
              <ul>
                <li>Immediate and permanent ban</li>
                <li>Forfeiture of escrowed funds</li>
                <li>Reporting to relevant partners or authorities (if necessary)</li>
              </ul>
            </section>

            <section className="tos-section">
              <h2>5. Scamming = Instant Loss of Funds</h2>
              <p>If you attempt to:</p>
              <ul>
                <li>Scam</li>
                <li>Deceive</li>
                <li>Provide fake or altered evidence</li>
                <li>Tamper with AutoMM functions</li>
                <li>Dispute trades you agreed to</li>
                <li>Pretend not to receive items</li>
                <li>Create false claims</li>
                <li>Ghost or delay intentionally</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>Afroo reserves the right to:</p>
              <ul>
                <li>Award all escrowed funds to the victim</li>
                <li>Permanently ban you</li>
                <li>Submit evidence to third-party services</li>
                <li>Restrict your access to Afroo services</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                <strong>All decisions are FINAL.</strong>
              </p>
            </section>

            <section className="tos-section">
              <h2>6. User Responsibility</h2>
              <p>By using AutoMM, you agree that YOU alone are responsible for:</p>
              <ul>
                <li>Verifying item legitimacy</li>
                <li>Verifying product quality</li>
                <li>Confirming digital goods work properly</li>
                <li>Confirming you received what you paid for</li>
                <li>Ensuring the trade is legal in your region</li>
                <li>Ensuring you understand what you are buying</li>
                <li>Ensuring you are sending to the correct escrow/instructions</li>
                <li>Ensuring you are trading with reputable members</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                Afroo cannot and will not confirm authenticity or value.
              </p>
            </section>

            <section className="tos-section">
              <h2>7. Lost Funds or Items</h2>
              <p>Afroo is not responsible for:</p>
              <ul>
                <li>Lost items held in escrow</li>
                <li>Lost crypto due to user error</li>
                <li>Wrong wallet addresses</li>
                <li>Wrong item transfers</li>
                <li>Blockchain delays</li>
                <li>Mistakes made by buyers or sellers</li>
                <li>Miscommunication between parties</li>
                <li>System outages or disruptions</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                <strong>All losses are the responsibility of the users involved.</strong>
              </p>
            </section>

            <section className="tos-section">
              <h2>8. Disputes</h2>
              <p>If a dispute arises, AutoMM Admin may step in to review:</p>
              <ul>
                <li>Chat logs</li>
                <li>Evidence</li>
                <li>Screenshots</li>
                <li>Transaction IDs</li>
                <li>Bot logs</li>
                <li>Timestamps</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>Admin's decision:</p>
              <ul>
                <li>Is final</li>
                <li>Cannot be appealed</li>
                <li>Cannot be contested</li>
                <li>May result in forfeiture of funds</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                Admin determines who receives escrow funds or whether funds are seized.
              </p>
            </section>

            <section className="tos-section">
              <h2>9. Prohibited Behavior</h2>
              <p>The following strictly prohibited behaviors result in instant ban and forfeiture:</p>
              <ul>
                <li>Bypassing AutoMM</li>
                <li>Attempting to scam</li>
                <li>Fake proof</li>
                <li>Forged screenshots</li>
                <li>Threats or harassment</li>
                <li>Fake disputes</li>
                <li>Using unverified alternate accounts</li>
                <li>Trading illegal goods, services, or banned items</li>
                <li>Blackmail or extortion</li>
                <li>Misuse of information obtained during the trade</li>
                <li>Using escrow to hide fraudulent intent</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                <strong>All violators will be permanently removed.</strong>
              </p>
            </section>

            <section className="tos-section">
              <h2>10. No Guarantees, Warranties, or Promises</h2>
              <p>AutoMM is provided as-is, without:</p>
              <ul>
                <li>Warranty of item quality</li>
                <li>Warranty of trade fairness</li>
                <li>Warranty of delivery</li>
                <li>Guarantee of authenticity</li>
                <li>Promise of safety or recovery</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>Afroo cannot recover:</p>
              <ul>
                <li>Items lost outside escrow</li>
                <li>Funds lost outside escrow</li>
                <li>Digital keys that don't work</li>
                <li>Fake accounts</li>
                <li>Misrepresented products</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                <strong>Use AutoMM at your own risk.</strong>
              </p>
            </section>

            <section className="tos-section">
              <h2>11. Evidence & Data Usage</h2>
              <p>By using AutoMM, you consent to Afroo using:</p>
              <ul>
                <li>Chat logs</li>
                <li>Bot logs</li>
                <li>Transaction evidence</li>
                <li>Images</li>
                <li>Screenshots</li>
                <li>Metadata</li>
                <li>Wallet addresses</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>For:</p>
              <ul>
                <li>Dispute resolution</li>
                <li>Anti-scam protection</li>
                <li>Fraud prevention</li>
                <li>Enforcement decisions</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>Evidence may be provided to:</p>
              <ul>
                <li>Discord Trust & Safety</li>
                <li>Third-party services</li>
                <li>Payment processors</li>
                <li>Law enforcement (if required)</li>
              </ul>
            </section>

            <section className="tos-section">
              <h2>12. Termination & Enforcement</h2>
              <p>Afroo may:</p>
              <ul>
                <li>Suspend accounts</li>
                <li>Ban users</li>
                <li>Restrict access</li>
                <li>Seize escrow funds</li>
                <li>Report rule violations</li>
                <li>Modify AutoMM Terms at any time</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                Using AutoMM after changes means you accept the updated terms.
              </p>
            </section>

            <section className="tos-section">
              <h2>13. Final Disclaimer</h2>
              <p>
                AutoMM is only a convenience tool designed to reduce scams. It does not make trades safe, guarantee outcomes, or
                ensure product legitimacy.
              </p>
              <p style={{ marginTop: '1rem' }}>
                <strong>All trades are YOUR responsibility, not Afroo's.</strong>
              </p>
            </section>
          </div>
        );

      case 'exchanger':
        return (
          <div className="tos-content">
            <div style={{ marginBottom: '2rem', padding: '1rem', background: 'rgba(168, 131, 255, 0.1)', borderRadius: '0.5rem', border: '1px solid rgba(168, 131, 255, 0.3)' }}>
              <p style={{ margin: 0 }}>
                These Exchanger Rules govern all users designated as "Exchangers" on Afroo. By applying for or operating as an Exchanger,
                you agree to: <strong>General TOS, P2P TOS, AutoMM TOS (if used), Crypto Swap TOS, these Extended Exchanger Rules, any
                ticket-level Terms, and any admin instructions (verbal or written).</strong> Failure to follow any rule may result in
                instant termination, permanent ban, and forfeiture of ALL exchanger funds.
              </p>
            </div>

            <section className="tos-section">
              <h2>Section 1 — Exchanger Status (No Rights)</h2>
              <p>Being approved as an Exchanger:</p>
              <ul>
                <li>Does NOT make you staff</li>
                <li>Does NOT make you a partner</li>
                <li>Does NOT grant authority</li>
                <li>Does NOT provide income guarantees</li>
                <li>Does NOT entitle you to vote on decisions</li>
                <li>Does NOT protect you from penalties</li>
                <li>Does NOT exempt you from any Afroo rules</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                <strong>You simply have permission to handle P2P exchange tickets.</strong>
              </p>
            </section>

            <section className="tos-section">
              <h2>Section 2 — Admin Seizure & Financial Authority</h2>
              <p>You agree that Admin may seize, withdraw, confiscate, redistribute, or utilize ANY exchanger deposit or escrow balance
              at ANY TIME for:</p>
              <ul>
                <li>Refunds</li>
                <li>Disputes</li>
                <li>Chargeback defense</li>
                <li>Platform losses</li>
                <li>Server profit</li>
                <li>Client protection</li>
                <li>Fraud mitigation</li>
                <li>Penalties</li>
                <li>Administrative needs</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                <strong>This financial authority is absolute, final, and irreversible. You waive ALL claims against Afroo regarding seized balances.</strong>
              </p>
            </section>

            <section className="tos-section">
              <h2>Section 3 — Role & Responsibilities</h2>
              <p>Exchangers must:</p>
              <ul>
                <li>Follow ALL Afroo rules</li>
                <li>Follow ALL admin instructions</li>
                <li>Follow ALL ticket requirements</li>
                <li>Handle trades promptly and accurately</li>
                <li>Use ONLY the official systems</li>
                <li>Behave professionally at all times</li>
              </ul>
            </section>

            <section className="tos-section">
              <h2>Section 4 — Communication Standards</h2>
              <p>You must:</p>
              <ul>
                <li>Respond to tickets within 5 minutes</li>
                <li>Maintain calm & professional wording</li>
                <li>Never argue with clients</li>
                <li>Never insult or escalate</li>
                <li>Always communicate through Afroo channels</li>
                <li>Provide clear instructions</li>
                <li>Never beg, provoke, or threaten</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                Unprofessional conduct = disciplinary action or termination.
              </p>
            </section>

            <section className="tos-section">
              <h2>Section 5 — Payment Method Rules</h2>
              <p>You must:</p>
              <ul>
                <li>Clearly list accepted payment methods</li>
                <li>Never change methods during a ticket</li>
                <li>Never accept reversible payments unless confident</li>
                <li>Always verify payment authenticity</li>
                <li>Refuse suspicious payments</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                You are fully liable for any payment method you choose to accept.
              </p>
            </section>

            <section className="tos-section">
              <h2>Section 6 — Escrow Requirements (Mandatory)</h2>
              <p>ALL trades must:</p>
              <ul>
                <li>Use Afroo Escrow</li>
                <li>Follow automated flow</li>
                <li>Deposit crypto before trade begins</li>
                <li>Never bypass escrow</li>
                <li>Never accept "off escrow" trades</li>
                <li>Never negotiate outside the system</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                <strong>Escrow bypass = instant ban + full seizure.</strong>
              </p>
            </section>

            <section className="tos-section">
              <h2>Section 7 — Fraud & Zero-Tolerance Violations</h2>
              <p>The following result in instant lifetime ban + full fund seizure:</p>
              <ul>
                <li>Attempting to scam</li>
                <li>Providing fake proof</li>
                <li>Fake chargebacks</li>
                <li>Collusion with clients</li>
                <li>Altering screenshots</li>
                <li>Lying about payments</li>
                <li>Manipulating rates</li>
                <li>Taking trades outside the system</li>
                <li>Using alts to boost yourself</li>
                <li>Any fraud or deception</li>
              </ul>
            </section>

            <section className="tos-section">
              <h2>Section 8 — Rate Transparency</h2>
              <p>Exchangers must:</p>
              <ul>
                <li>Display accurate rates</li>
                <li>Disclose ALL fees upfront</li>
                <li>Never change rates mid-trade</li>
                <li>Honor quoted rates once escrow activates</li>
                <li>Provide breakdown upon request</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                Rate manipulation = termination.
              </p>
            </section>

            <section className="tos-section">
              <h2>Section 9 — Transaction Processing</h2>
              <p>Exchangers must:</p>
              <ul>
                <li>Complete trades within 30–60 minutes</li>
                <li>Verify payment BEFORE release</li>
                <li>Document every trade with proof</li>
                <li>Report suspicious users immediately</li>
                <li>Never rush or pressure clients</li>
                <li>Never release without absolute confirmation</li>
              </ul>
            </section>

            <section className="tos-section">
              <h2>Section 10 — Dispute Obligations</h2>
              <p>Exchangers must:</p>
              <ul>
                <li>Fully cooperate with Admin</li>
                <li>Provide requested proof within 24 hours</li>
                <li>Accept Admin decisions as final</li>
                <li>Maintain logs for 90 days minimum</li>
                <li>Never argue with or appeal Admin rulings</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                <strong>Admin rulings override all other conditions.</strong>
              </p>
            </section>

            <section className="tos-section">
              <h2>Section 11 — Chargeback & External Disputes</h2>
              <p>If YOU receive a chargeback:</p>
              <ul>
                <li>Afroo is NOT responsible</li>
                <li>Afroo will NOT reimburse you</li>
                <li>Afroo may seize your funds</li>
                <li>You may request transcripts to defend yourself</li>
                <li>You understand fiat methods are high-risk</li>
              </ul>
            </section>

            <section className="tos-section">
              <h2>Section 12 — Privacy Requirements</h2>
              <p>You must protect all client data: payment screenshots, wallet addresses, names, account IDs, private messages.</p>
              <p style={{ marginTop: '1rem' }}>You may NOT:</p>
              <ul>
                <li>Leak</li>
                <li>Sell</li>
                <li>Share</li>
                <li>Threaten</li>
                <li>Publicly expose</li>
                <li>Collect unneeded data</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                <strong>Privacy violations = immediate lifetime ban.</strong>
              </p>
            </section>

            <section className="tos-section">
              <h2>Section 13 — KYC / AML & Legal Compliance</h2>
              <p>You must:</p>
              <ul>
                <li>Complete KYC/AML if required</li>
                <li>Follow local laws</li>
                <li>Refuse illegal funds</li>
                <li>Report suspicious behavior</li>
                <li>Not aid tax evasion or laundering</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                Failing to follow AML rules = instant removal.
              </p>
            </section>

            <section className="tos-section">
              <h2>Section 14 — Technical Requirements</h2>
              <p>Exchangers MUST maintain:</p>
              <ul>
                <li>Stable internet</li>
                <li>Active Discord account</li>
                <li>Notifications on</li>
                <li>Secure crypto wallets</li>
                <li>Backup devices (optional but recommended)</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                Repeated technical issues = demotion or removal.
              </p>
            </section>

            <section className="tos-section">
              <h2>Section 15 — Availability Rules</h2>
              <p>You must:</p>
              <ul>
                <li>Clearly state operating hours</li>
                <li>Use "away mode" when offline</li>
                <li>Not accept tickets you cannot complete</li>
                <li>Avoid ghosting clients</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                Ghosting = penalties or removal.
              </p>
            </section>

            <section className="tos-section">
              <h2>Section 16 — Reputation System</h2>
              <p>Your reputation score considers: completion rate, dispute rate, response speed, client feedback, professionalism,
              activity level, and compliance.</p>
              <p style={{ marginTop: '1rem' }}>
                Low reputation = reduced visibility or removal.
              </p>
            </section>

            <section className="tos-section">
              <h2>Section 17 — Multi-Account Restrictions</h2>
              <p>Exchangers may NOT:</p>
              <ul>
                <li>Operate multiple exchanger accounts</li>
                <li>Share accounts</li>
                <li>Switch between identities</li>
                <li>Use alt accounts to trade or review themselves</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                <strong>Violation = full ban + fund seizure.</strong>
              </p>
            </section>

            <section className="tos-section">
              <h2>Section 18 — Client Verification</h2>
              <p>Exchangers may request: payment proof, identification (non-sensitive), transaction logs, additional confirmation in
              high-risk trades. Verification must be reasonable and non-discriminatory.</p>
            </section>

            <section className="tos-section">
              <h2>Section 19 — Cancellation Rules</h2>
              <ul>
                <li>Clients may cancel before escrow deposit</li>
                <li>Exchangers must provide valid reasons to cancel after escrow</li>
                <li>Repeated cancellations = reputation penalties</li>
              </ul>
            </section>

            <section className="tos-section">
              <h2>Section 20 — Fraud Prevention Duties</h2>
              <p>You must: verify senders, double-check reversibility, watch for stolen accounts, avoid known scammers, report suspicious
              behavior. Failure to prevent fraud = exchanger liability.</p>
            </section>

            <section className="tos-section">
              <h2>Section 21 — Balance Requirements</h2>
              <p>You must maintain: sufficient crypto liquidity, minimum asset thresholds, stable reserves. Insufficient liquidity =
              deactivation or penalties.</p>
            </section>

            <section className="tos-section">
              <h2>Section 22 — Fee Structure</h2>
              <p>Platform fees: apply to all exchanger trades, are deducted automatically, may change anytime, must NOT be bypassed.
              Fee evasion = instant termination.</p>
            </section>

            <section className="tos-section">
              <h2>Section 23 — Liquidity Obligations</h2>
              <p>Exchangers must: maintain active liquidity, avoid repeated "out of stock" status, not mislead about available supply.</p>
            </section>

            <section className="tos-section">
              <h2>Section 24 — Quality Assurance & Audits</h2>
              <p>Afroo conducts: random audits, ticket reviews, performance checks, behavior monitoring, client feedback analysis.
              You MUST cooperate with audits.</p>
            </section>

            <section className="tos-section">
              <h2>Section 25 — Marketing, Advertising & Public Behavior</h2>
              <p>Exchangers may NOT: advertise rates outside approval, make false claims, promote themselves as "staff", misrepresent
              the Afroo brand. You must ALWAYS make it clear you are not staff.</p>
            </section>

            <section className="tos-section">
              <h2>Section 26 — Fair Competition Rules</h2>
              <p>You may NOT: collude with other exchangers, fix rates, poach clients, bribe clients, manipulate reputation.
              Anti-competitive behavior = instant removal.</p>
            </section>

            <section className="tos-section">
              <h2>Section 27 — Logging & Record Keeping</h2>
              <p>You MUST: keep trade logs, store payment screenshots, retain evidence for 90 days, provide documentation upon request.</p>
            </section>

            <section className="tos-section">
              <h2>Section 28 — System Misuse</h2>
              <p>Forbidden actions: exploiting the bot, attempting to hack or bypass systems, abusing ticket creation, causing artificial
              delays, manipulating escrow.</p>
            </section>

            <section className="tos-section">
              <h2>Section 29 — Abuse of Power</h2>
              <p>Exchangers may NOT: intimidate clients, threaten negative reputation, force trades, abuse position to win disputes.
              Admin will revoke status immediately.</p>
            </section>

            <section className="tos-section">
              <h2>Section 30 — Training & Knowledge Requirements</h2>
              <p>Exchangers must: understand every Afroo rule, know how escrow works, know how disputes work, understand payment risks,
              be familiar with crypto networks. Ignorance does NOT excuse violations.</p>
            </section>

            <section className="tos-section">
              <h2>Section 31 — Public Image & Brand Protection</h2>
              <p>Exchangers must: avoid drama, avoid harassing anyone publicly, avoid defaming Afroo or other exchangers, avoid leaking
              internal conversations. Damaging the brand = removal.</p>
            </section>

            <section className="tos-section">
              <h2>Section 32 — Emergency Admin Powers</h2>
              <p>Admin may: freeze exchanger accounts, hold all funds, take over tickets, halt withdrawals, remove access, invalid all
              trades. This can happen at ANY time, with NO notice.</p>
            </section>

            <section className="tos-section">
              <h2>Section 33 — Suspension & Penalties</h2>
              <p>Penalty structure:</p>
              <ul>
                <li>1st Offense → Warning</li>
                <li>2nd Offense → 7–30 day suspension</li>
                <li>3rd Offense → Permanent ban + fund seizure</li>
                <li>Severe Offense → Immediate termination</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                Admin discretion overrides these tiers.
              </p>
            </section>

            <section className="tos-section">
              <h2>Section 34 — Termination Conditions</h2>
              <p>Termination occurs for: scamming, unprofessional behavior, chargebacks, abuse, repeated poor performance, AML violations,
              ban evasion, escrow bypass, any action deemed harmful to Afroo.</p>
            </section>

            <section className="tos-section">
              <h2>Section 35 — Post-Termination Obligations</h2>
              <p>After losing privileges, you must: complete pending refunds, provide evidence for disputes, not interfere with Afroo
              operations, not contact clients for retaliation, not impersonate exchangers.</p>
            </section>

            <section className="tos-section">
              <h2>Section 36 — No Liability</h2>
              <p>Afroo is NOT liable for: your financial losses, chargebacks, payment reversals, fraud committed against you, misuse
              of fiat methods, lost items or funds. You assume full personal financial risk as an Exchanger.</p>
            </section>

            <section className="tos-section">
              <h2>Section 37 — Independent Actor Status</h2>
              <p>Exchangers are NOT: employees, contractors, affiliates, legal representatives, support agents. You are an independent
              participant under Afroo's rules.</p>
            </section>

            <section className="tos-section">
              <h2>Section 38 — Conflict of Interest</h2>
              <p>You MUST disclose if: you trade with close friends, you trade with alt accounts, you trade with known risky users,
              a trade could bias your decisions. Non-disclosure = termination.</p>
            </section>

            <section className="tos-section">
              <h2>Section 39 — Platform Updates</h2>
              <p>You must stay updated on: policy changes, fee changes, new features, technical updates, compliance requirements.
              Claiming "I didn't know" is not accepted.</p>
            </section>

            <section className="tos-section">
              <h2>Section 40 — Agreement Acceptance</h2>
              <p>By continuing as an Exchanger, you:</p>
              <ul>
                <li>Acknowledge all 40 rules</li>
                <li>Accept all seizure rights</li>
                <li>Accept all admin powers</li>
                <li>Accept all penalties</li>
                <li>Accept no financial guarantee</li>
                <li>Accept full responsibility for all transactions</li>
              </ul>
              <p style={{ marginTop: '1rem' }}>
                <strong>This constitutes a binding agreement between you and Afroo.</strong>
              </p>
            </section>
          </div>
        );
    }
  };

  return (
    <div className="min-h-screen relative" style={{ background: 'radial-gradient(circle at top right, #1c1528 0%, #0d0b14 70%)' }}>
      <Navbar />

      <div className="container mx-auto px-4 md:px-6 pt-24 md:pt-32 pb-12 md:pb-20">
        {/* Header */}
        <div className="mb-10 md:mb-14 text-center max-w-4xl mx-auto">
          <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold mb-4 bg-gradient-to-r from-[#d7c6ff] via-[#a883ff] to-[#6d35ff] bg-clip-text text-transparent">
            Terms of Service
          </h1>
          <p className="text-base md:text-lg mb-2" style={{ color: '#b0adc0' }}>
            Legal framework governing platform use
          </p>
          {mounted && (
            <p className="text-sm" style={{ color: '#9693a8' }}>
              Effective: {new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
            </p>
          )}
        </div>

        {/* Tabs */}
        <div className="flex flex-wrap justify-center gap-3 mb-10">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className="tos-tab"
              style={{
                background: activeTab === tab.id
                  ? 'linear-gradient(135deg, rgba(168, 131, 255, 0.2), rgba(109, 53, 255, 0.2))'
                  : 'rgba(255, 255, 255, 0.03)',
                border: activeTab === tab.id
                  ? '1px solid rgba(160, 120, 255, 0.4)'
                  : '1px solid rgba(160, 120, 255, 0.15)',
                color: activeTab === tab.id ? 'white' : '#b0adc0'
              }}
            >
              <span className="font-semibold">{tab.name}</span>
            </button>
          ))}
        </div>

        {/* TOS Content */}
        <div className="max-w-4xl mx-auto">
          <div className="tos-container animate-fadeIn">
            {getTOSContent(activeTab)}
          </div>

          {/* Footer Notice */}
          <div className="mt-8 p-6 rounded-xl text-center" style={{
            background: 'rgba(168, 131, 255, 0.08)',
            border: '1px solid rgba(160, 120, 255, 0.2)'
          }}>
            <p className="text-sm md:text-base font-medium text-white mb-2">
              By using Afroo Exchange, you acknowledge reading and accepting these terms.
            </p>
            <p className="text-xs md:text-sm" style={{ color: '#b0adc0' }}>
              Questions? Contact support via Discord or platform ticket system.
            </p>
          </div>
        </div>
      </div>

      <style jsx>{`
        .tos-tab {
          padding: 0.875rem 1.5rem;
          border-radius: 0.75rem;
          transition: all 0.3s ease;
          cursor: pointer;
          backdrop-filter: blur(20px);
          font-size: 0.9375rem;
        }

        .tos-tab:hover {
          transform: translateY(-2px);
          box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
        }

        .tos-container {
          padding: 2.5rem;
          background: rgba(255, 255, 255, 0.02);
          backdrop-filter: blur(20px);
          border: 1px solid rgba(160, 120, 255, 0.2);
          border-radius: 1.25rem;
        }

        .tos-content {
          color: #e8e6f0;
        }

        .tos-section {
          margin-bottom: 2.5rem;
        }

        .tos-section:last-child {
          margin-bottom: 0;
        }

        .tos-section h2 {
          font-size: 1.125rem;
          font-weight: 700;
          color: #ffffff;
          margin-bottom: 0.875rem;
          letter-spacing: -0.01em;
        }

        .tos-section p {
          line-height: 1.75;
          color: #d0cedd;
          margin-bottom: 0.875rem;
        }

        .tos-section ul {
          list-style: none;
          margin-left: 0;
          margin-top: 0.75rem;
          color: #d0cedd;
        }

        .tos-section li {
          line-height: 1.75;
          margin-bottom: 0.625rem;
          padding-left: 1.5rem;
          position: relative;
        }

        .tos-section li:before {
          content: "•";
          position: absolute;
          left: 0.5rem;
          color: #a883ff;
          font-weight: bold;
        }

        .animate-fadeIn {
          animation: fadeIn 0.4s ease-out;
        }

        @keyframes fadeIn {
          from {
            opacity: 0;
            transform: translateY(8px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        @media (max-width: 768px) {
          .tos-tab {
            padding: 0.75rem 1.25rem;
            font-size: 0.875rem;
          }

          .tos-container {
            padding: 1.75rem;
          }

          .tos-section h2 {
            font-size: 1rem;
          }

          .tos-section p,
          .tos-section li {
            font-size: 0.9375rem;
            line-height: 1.7;
          }
        }
      `}</style>
    </div>
  );
}
