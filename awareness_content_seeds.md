# Guardian – Cybersecurity Awareness Content Library

> **Note (2026-11-06).** These seed articles come from Guardian's earlier workplace version (staff audience, insider
> threat categories). Analysts can still use them as source material. Family topics for parents and children are now
> written through the analyst workspace's "Family versions" step (see [plan.md §8.0](plan.md)).

Each article is written for an admin audience. The admin reads, selects relevant portions,
writes a summary, and delivers it to staff with the engagement type of their choice.

Threat categories: `all` | `negligent` | `malicious` | `compromised` | `third_party`

---

## 1. Phishing Email Recognition
**Threat category:** `all`

Phishing remains the single most common entry point for security incidents worldwide. The Verizon Data Breach Investigations Report consistently places phishing as the initiating action in over 30% of confirmed breaches. Understanding how phishing works, mechanically, psychologically, and technically, is the foundation of any awareness programme.

### How Phishing Works

A phishing email is designed to deceive the recipient into taking an action that benefits the attacker: clicking a link, opening an attachment, entering credentials, or transferring money. The deception operates on multiple levels simultaneously.

At the technical level, attackers manipulate sender addresses using techniques like display-name spoofing (where the visible name says "IT Support" but the actual address is attacker@gmail.com), lookalike domains (microsofft.com, paypa1.com), and subdomain abuse (login.microsoft.com.attacker.net, the real domain here is attacker.net, not microsoft.com). Many email clients show only the display name by default, hiding the actual sending address unless the recipient explicitly looks.

At the psychological level, phishing exploits six well-documented principles of influence identified by psychologist Robert Cialdini: authority (the email appears to come from a senior figure or trusted institution), urgency (act now or your account will be suspended), scarcity (limited-time offer, last warning), social proof (your colleagues have already verified their accounts), liking (the email is friendly and personalised), and reciprocity (a gift or benefit is offered in exchange for an action). Most phishing emails trigger at least three of these simultaneously.

### Patterns to Recognise

**Spear phishing** is targeted phishing where the attacker has researched the recipient. They may know the victim's name, job title, manager's name, and current projects, often harvested from LinkedIn or company websites. These emails feel personal and credible because they reference real context. Generic phishing casts a wide net; spear phishing is a sniper shot.

**Whaling** targets senior executives. The financial stakes are higher and the attacker invests more effort in research and social engineering. An email to a CFO appearing to come from the CEO requesting an urgent wire transfer is a classic whaling pattern.

**Clone phishing** involves duplicating a legitimate email the recipient has previously received, replacing the links or attachments with malicious ones, and re-sending it with a plausible explanation ("resending with corrected attachment").

**Smishing and vishing** are the SMS and voice-call equivalents. As email security tools improve, attackers increasingly pivot to these channels where users have fewer trained instincts and fewer technical defences.

### The Anatomy of a Malicious Link

Before clicking any link, examine it. Hover over the link to reveal the actual destination URL (in most email clients and browsers the real URL appears in the status bar). Look for: domain mismatches (the visible text says one thing, the actual URL is different), excessive subdomains, URL-shorteners (bit.ly, tinyurl, these hide the destination), and unusual top-level domains (.xyz, .top, .ru where you'd expect .com or .org).

HTTPS does not mean safe. A malicious website can have a valid SSL certificate. The padlock icon means the connection is encrypted, it says nothing about whether the site is legitimate.

### Attachment Threats

Malicious attachments commonly use Office documents with macros (enabling macros executes attacker code), PDFs with embedded JavaScript or links to phishing pages, archives (.zip, .rar) containing executables, and ISO files that mount as virtual drives to bypass some security controls. A file named invoice.pdf.exe is an executable, Windows hides known extensions by default, making this a reliable trick. File icons can also be faked; an executable can be made to look like a PDF icon.

### What To Do

The correct response to a suspicious email is: do not click, do not reply, do not forward to colleagues to ask their opinion (forwarding propagates the threat), and report it to the security or IT team using the designated reporting mechanism. Most organisations use a "report phishing" button in the email client or a dedicated email address.

If you have already clicked a link or opened an attachment, report it immediately regardless of whether anything appeared to happen. Many malicious payloads are silent and operate in the background. The speed of reporting is the single most important factor in limiting damage.

### Developing a Sceptical Mindset

Security professionals use the phrase "trust but verify." For email, the bar should be higher: verify, then trust. Any email requesting unusual action, transferring funds, providing credentials, installing software, opening an attachment, should be verified through a separate channel. Call the sender using a phone number you already have, not one provided in the suspicious email. Walk to their desk. Send a new email to their known address (not by replying to the suspicious one).

Organisations with high phishing resilience share one common trait: they have normalised the act of questioning and verifying requests. Employees who ask "is this legitimate?" are not being difficult, they are doing exactly what a security-aware culture demands.

---

## 2. Password Hygiene and Password Managers
**Threat category:** `negligent`

Passwords are the most commonly compromised form of authentication, and the reason is almost never technical sophistication, it is human behaviour. Understanding why passwords fail and what genuinely makes them strong is the starting point for building durable habits.

### Why Passwords Get Compromised

**Credential stuffing** is an automated attack where stolen username/password pairs from one breach are systematically tested against other services. When a gaming website is breached and millions of credentials are leaked, attackers run those exact credentials against banking sites, corporate VPNs, and email services. If you use the same password for your work email as you do for a breached personal account, the attacker has your work email access without ever targeting your organisation.

The scale of credential theft is staggering. The "Have I Been Pwned" database, maintained by security researcher Troy Hunt, contained over 12 billion records from known breaches as of 2024. The probability that at least one of your personal accounts has been included in a breach is very high.

**Brute force attacks** systematically try all possible passwords. A modern GPU-based cracking rig can test billions of passwords per second against an offline hash. An eight-character password using only lowercase letters has approximately 200 billion combinations, sounds large, but it falls in under a minute with modern hardware. Adding one uppercase letter, one digit, and one symbol brings that to many quadrillions of combinations, but the real problem is that most people do not create truly random passwords.

**Predictable patterns** are exploited by dictionary attacks, which test not just dictionary words but common substitutions (p@ssw0rd), keyboard patterns (qwerty123), and structural patterns (Month+Year, Season+Year, Name+Number). Security researchers have catalogued these patterns extensively, and password cracking tools include them as rule sets.

### What Makes a Password Strong

Length is the single most powerful factor. A 16-character passphrase made of four random common words (correct-horse-battery-staple is the famous example from XKCD) is computationally harder to crack than an 8-character complex password and far easier to remember. The maths: length increases the search space exponentially.

True randomness matters. Humans are predictably bad at generating random sequences. We gravitate toward meaningful dates, names, patterns, and words with emotional resonance. A password that feels random to you is often highly predictable to a trained attacker.

### The Case for Password Managers

A password manager solves the human problem by generating truly random, unique, long passwords for every account and storing them in an encrypted vault. You need to remember only one strong master password. The benefits:

- Every account gets a unique password, eliminating credential stuffing risk
- Passwords are long and random, eliminating brute force feasibility
- Auto-fill detects domain mismatches, providing phishing resistance (a password manager will not auto-fill credentials on microsofft.com)
- Passwords can be audited for reuse, weakness, and known-breach inclusion

Enterprise password managers add features like vault sharing for team accounts, access logging, emergency access, and central administration.

### Myths That Create Vulnerability

**"I change my password regularly so I'm safe."** Mandatory periodic password changes, without a breach trigger, actually reduce security. People respond to forced changes by incrementing a number (Password1 → Password2) or making minimal alterations. NIST (National Institute of Standards and Technology) revised its guidelines in 2017 to recommend against mandatory periodic changes in favour of changing passwords only when compromise is suspected.

**"I can tell if my account is compromised."** Most credential compromises are silent. Attackers with access to an email account read and copy data without sending messages or making visible changes. You would not know.

**"My password is written in a way only I would understand."** Substitution ciphers, pig latin, and personal codes seem clever but follow patterns that appear in cracking rule sets.

### Multi-Factor Authentication as the Safety Net

Even a compromised password provides no access to an account protected by multi-factor authentication. MFA should be enabled on every account that offers it, prioritised in this order: corporate email and VPN, financial accounts, email accounts that can receive password resets, cloud storage, and all other services.

---

## 3. MFA Fatigue Attacks
**Threat category:** `compromised`

Multi-factor authentication dramatically raises the cost of account compromise. A stolen password alone is no longer sufficient, the attacker also needs the second factor. This has driven attackers to develop techniques that target MFA itself, with MFA fatigue (also called MFA bombing or push spam) being among the most effective and increasingly common.

### How MFA Fatigue Works

When a user's credentials are stolen and an MFA system sends a push notification for approval, the attacker cannot approve the notification themselves, only the device receiving it can. The MFA fatigue attack resolves this by sending a continuous stream of push notifications to the victim's device, hoping that:

1. The user, overwhelmed or confused, approves one simply to make the notifications stop
2. The user approves one late at night when half-asleep
3. The user mistakes the notifications for a system glitch and approves one
4. The attacker pairs the notification flood with a social engineering call, claiming to be IT support and asking the user to approve "a system update"

The 2022 Uber breach began with a contractor's credentials being purchased on the dark web. The attacker then flooded the contractor's phone with MFA push requests for over an hour. When the contractor did not approve, the attacker called them on WhatsApp, claimed to be from Uber IT security, and told them to approve the MFA request. The contractor complied. Uber's internal systems were then compromised.

### Why It Works Psychologically

The attack exploits several psychological vulnerabilities. **Alert fatigue** is a well-documented phenomenon where repeated alerts reduce individual attention to each alert, the same problem that affects radiologists reading hundreds of scans or security analysts reviewing thousands of log events. **Authority bias** is triggered when the attacker calls claiming to be IT support. **Compliance under pressure** causes people to take action just to resolve a persistent, annoying stimulus. The combination is highly effective.

### Recognising and Responding Correctly

An unexpected MFA push notification, one you did not initiate by attempting to log in, is a definitive sign that someone is using your credentials. The correct responses:

**Deny every request.** Never approve an MFA push you did not initiate. There is no legitimate scenario where IT would need you to approve an MFA request without you attempting a login.

**Do not engage with callers claiming to be IT.** If someone calls claiming to be from IT security and asks you to approve an MFA notification, hang up. Call your IT helpdesk using the official number listed in the company directory, not the number the caller provides.

**Report immediately.** Contact the security team even if you denied all requests. The attempt reveals that your credentials are compromised and must be changed immediately.

**Change your password from a clean device** before the attacker tries other methods.

### Number Matching: The Technical Defence

Many MFA systems now support number matching, where the push notification displays a two-digit code that the user must enter into the authenticator app, rather than simply approving with one tap. This breaks the MFA fatigue attack because the attacker cannot tell the user what code to enter, they would need to communicate the code displayed on the login screen, which would require a live social engineering call and would be obvious. Organisations should enable number matching wherever available.

### Patterns in Targeted Attacks

MFA fatigue is typically used against **compromised insiders**, employees whose credentials have been stolen through phishing, data breaches, or malware, rather than as a first-stage attack. Defenders should treat a cluster of denied MFA requests as a high-priority alert, investigate the source IP of the login attempt, and proactively rotate credentials for the targeted account.

---

## 4. Tailgating and Physical Access Control
**Threat category:** `malicious`

Digital security receives the most attention in awareness programmes, but physical access breaches remain a significant and underappreciated vector. An attacker who gains physical access to a server room, an unlocked workstation, or a filing cabinet can cause damage that no firewall can prevent.

### The Mechanics of Tailgating

Tailgating (also called piggybacking) is the act of following an authorised person through a secured door without presenting credentials. It exploits social courtesy, the deeply ingrained human instinct to hold doors open for people, particularly those who appear to be colleagues, are carrying items, or seem to belong.

Attackers exploit several cover stories: carrying boxes or equipment (making it implausible to badge in while hands are full), wearing company-branded clothing, carrying clipboards or wearing high-visibility vests (universal signals of "I'm meant to be here"), or simply walking with confidence and purpose. Research by security consultants shows that a confident, appropriately dressed person can walk into most offices with minimal challenge.

### Why Employees Enable Tailgating

Challenging an unfamiliar person feels socially uncomfortable and potentially confrontational. Employees fear seeming rude, paranoid, or obstructive. In organisations with a polite culture, the social cost of saying "could you badge in please?" feels higher than the perceived security risk of holding the door. This is compounded when the tailgater appears to have a legitimate reason, appears friendly, or the area does not seem particularly sensitive.

The security failure is cultural, not individual. Employees will follow the social norms of their environment. If no one ever challenges tailgaters, challenging tailgaters becomes abnormal behaviour.

### High-Risk Areas and Assets

Not all physical access is equally consequential. The highest-risk locations are: server rooms and network equipment closets, areas housing sensitive printed documents or physical storage media, workstations with access to privileged systems, reception areas where visitor sign-in logs can be photographed, and meeting rooms where confidential discussions occur and whiteboards are left visible.

### Malicious Insider Patterns

Physical security is particularly relevant to the **malicious insider** category. A disgruntled employee who knows that a colleague's access card works in a restricted area may borrow or clone that card to exfiltrate data or cause damage while creating a false alibi. A departing employee whose access should have been revoked may badge in after their last official day. An insider conducting reconnaissance for a future attack may photograph network infrastructure or office layouts under the cover of a routine visit.

Access control logs are among the most powerful forensic tools available. Every badge entry and exit creates a timestamped record. Unusual access patterns, an employee entering the server room at 2 AM, accessing areas outside their normal work zone, or entering on days they are not scheduled to work, are reliable indicators worth investigating.

### Correct Behaviours

Every employee is responsible for access control, not just security guards. The correct response when an unrecognised person attempts to follow you through a secured door is to ask them politely to badge in. This should be framed as policy compliance, not personal suspicion: "Sorry, policy requires everyone to badge through individually, do you have your access card?" If the person is legitimate, this takes ten seconds. If they are not, you may have prevented a breach.

Visitors must always be escorted. "Visitor" badges must be visually distinct from employee badges. Visitor sign-in logs must be maintained and reconciled. Visitors waiting in reception must not be left adjacent to unlocked workstations, printed documents, or sensitive whiteboard content.

---

## 5. Removable Media and USB Risks
**Threat category:** `all`

USB drives and removable media represent a dual threat: they can carry malware into an organisation, and they can carry sensitive data out. Both vectors are exploited by attackers and insiders alike, making this a relevant risk for every threat category.

### The Inbound Threat: Malware Delivery

When a USB drive is inserted into a computer, the operating system interacts with it before any security software can fully analyse it. Historically, Windows auto-run features allowed code on a USB drive to execute automatically on insertion. While modern operating systems have disabled auto-run by default, newer attack techniques remain effective.

**BadUSB** attacks reprogram the firmware of a USB device so that it presents itself to the host computer as a keyboard or network adapter rather than a storage device. A device impersonating a keyboard can type commands at machine speed, executing malware, opening backdoors, exfiltrating data, within seconds of insertion, before any endpoint security tool can react. The firmware manipulation is invisible to the operating system; the device appears legitimate in device manager.

**The dropped USB attack** (also called the "baited USB" or "lost USB" attack) is a social engineering technique where an attacker deliberately leaves one or more USB drives in a target organisation's car park, reception area, or bathroom. The drives are often labelled with enticing titles: "Salary Review Q4," "Redundancy List," or the company's name. Employees who pick them up and insert them into work machines out of curiosity, or with the intent to find the owner, execute the payload.

A University of Illinois study found that approximately 48% of randomly dropped USB drives were plugged into computers. The drives with labels indicating personal content had the highest insertion rate. Curiosity is a powerful and reliable attack vector.

### The Outbound Threat: Data Exfiltration

USB drives are a primary data exfiltration tool for malicious insiders. A drive holding 128GB can contain hundreds of thousands of documents, entire code repositories, or complete customer databases. Unlike network exfiltration, physical removal of data leaves no network logs. Without endpoint security controls that monitor and log USB insertions and file copies, an insider can walk out with an organisation's most sensitive assets with no technical evidence.

The pattern often seen in investigations: a departing employee who has decided to take intellectual property to a competitor inserts a USB drive in the days before their last day, copies specific files, and leaves. By the time the theft is discovered, often weeks later when the competitor begins using the stolen information, the drive is long gone.

### Negligent Risk: Personal Drives in Work Machines

Employees who use personal USB drives to move files between home and work computers create several risks without any malicious intent. Personal computers typically have weaker security controls, may be shared with family members, and may be infected with malware that silently copies data from connected drives or installs itself onto the work machine. An unencrypted personal drive left in a bag or car also creates a data breach risk if lost.

### Policy and Technical Controls

Effective management of USB risk requires both policy and technical enforcement. Policy alone, "do not use personal USB drives", is insufficient if there is no technical enforcement. Endpoint security solutions can be configured to block all USB storage devices, whitelist only IT-provisioned encrypted drives, log all USB insertions and file transfers, and alert the security team to unusual data volumes being copied.

All authorised removable media should be encrypted. If a drive is lost, encrypted content cannot be read without the encryption key.

---

## 6. Oversharing on Social Media and LinkedIn
**Threat category:** `negligent`

Open-source intelligence (OSINT), the collection and analysis of publicly available information, is a standard first step in most targeted attacks. Before sending a spear-phishing email, before attempting to social engineer a receptionist, before crafting a pretexting scenario, an attacker researches the target using publicly available information. The primary sources are LinkedIn, Twitter/X, Facebook, and company websites. Employees who overshare make this research dramatically easier.

### What Attackers Learn from Social Media

From a single well-maintained LinkedIn profile, an attacker can determine: the employee's full name, job title, employer, department, tenure, career history, educational background, professional skills, the software tools and platforms they use (often listed as skills), their manager's name (via "reports to" inference), their direct reports, colleagues they interact with publicly, and sometimes their current projects or clients (mentioned in posts or recommendations).

From Twitter/X and Facebook: travel plans ("heading to the Singapore conference next week"), physical location data (tagged photos revealing the office layout, team photos), personal relationships (family members who can be impersonated), and opinions about the employer (indicating grievances that could be exploited).

From company websites: organisational charts, email address formats (firstname.lastname@company.com), names of senior leaders, office locations, technology partners, and press releases that reveal strategic initiatives.

An attacker synthesising this information can construct a spear-phishing email that references a real project, names a real colleague, uses the correct email format, and arrives at a plausible moment. The recipient has almost no reason to be suspicious.

### The Organisational Chart Problem

Employees who list their full team hierarchy on LinkedIn, manager, direct reports, peers, are publishing an organisational chart that attackers can use to impersonate management. If an attacker knows that the CFO's name is Michelle, that Michelle's PA is David, and that David handles wire transfer approvals, they can craft a BEC (Business Email Compromise) attack with detailed, convincing context.

### Photography and Video Risks

Photos taken inside the office and posted on social media frequently reveal: network equipment and cable runs, whiteboard content showing project plans or architecture diagrams, screens showing internal applications, access control panel locations, and security camera positions. Video calls where a background is not blurred can reveal home office setups, personal information, and, if recorded, audio of sensitive discussions.

### Professional Practices for Social Media

The goal is not to eliminate a professional online presence, LinkedIn is a legitimate career tool. The goal is to share deliberately. Specific practices: avoid naming internal project names, code names, or client names in posts. Do not list internal tools, software, or systems as skills if those are not publicly known. Do not publish travel plans in advance. Blur or crop backgrounds in photos before posting. Review privacy settings on personal accounts regularly. Do not accept connection requests from unknown individuals claiming to be colleagues, recruiters, or industry contacts without verifying through a second channel.

---

## 7. Shadow IT – Unauthorised Apps and Cloud Storage
**Threat category:** `negligent`

Shadow IT refers to hardware, software, and cloud services used by employees without the knowledge or approval of the IT department. It is overwhelmingly driven by good intentions, employees trying to work more efficiently, but it creates security, compliance, and operational risks that the organisation cannot manage because it does not know the exposure exists.

### Why Shadow IT Happens

IT approval processes are often perceived as slow, bureaucratic, and disconnected from operational reality. A marketing team that needs to share large files with an agency cannot wait two weeks for IT to provision an approved solution, so they use personal Dropbox. A developer who finds an internal code review tool frustrating installs a browser extension that offers the same functionality. A finance employee who needs to analyse data on a tight deadline exports it to a personal Google Sheet where the formulas work the way they need them to.

The problem is not the employee's intent, it is the gap between what IT provides and what teams actually need. Effective shadow IT reduction requires both policy and a commitment to making approved alternatives genuinely better than the shadow alternatives.

### The Security Risks

**Data leaving the perimeter.** When an employee copies sensitive data to a personal cloud storage account, that data is now subject to the security controls of the personal account, which typically means a single password, no audit trail, potential data sharing with family members, and no corporate backup or recovery. The organisation has lost visibility and control of that data entirely.

**Excessive application permissions.** Many free web applications and browser extensions request extensive permissions: access to all data on websites you visit, access to your email, access to clipboard content. A browser extension installed without IT review may be harvesting every piece of data the user types or views, including credentials, sensitive documents, and customer data.

**No audit trail.** When sensitive data is processed through an unsanctioned tool, there is no log that the organisation can access. In the event of a breach or regulatory inquiry, the organisation cannot demonstrate what happened to data it did not know was being processed.

**Vendor security posture.** Approved vendors are vetted for security practices, data protection commitments, and regulatory compliance. Unsanctioned vendors have not been assessed. A free online tool that processes payroll data may store that data in a jurisdiction with no data protection law.

### Common Shadow IT Examples

File sharing: personal Dropbox, Google Drive, WeTransfer. Communication: personal WhatsApp groups for work discussions. Productivity: personal Notion, Airtable, or similar tools containing work data. Development: unapproved npm packages, browser extensions, AI tools processing code. Finance: personal spreadsheet tools processing payroll or financial projections.

### Reporting and Requesting Tools

The correct response when an employee needs a tool that IT has not provisioned is to request it through the official channel. If the approval process is the problem, that is a process problem to be raised with management, not a reason to use unsanctioned tools. Employees who are uncertain whether a tool they are already using is approved should ask IT without fear of consequence.

---

## 8. Email Forwarding to Personal Accounts
**Threat category:** `malicious`

Automatically forwarding corporate email to a personal email account is a behaviour that straddles the line between convenience and serious policy violation, and in its more deliberate forms represents one of the clearest patterns of malicious insider activity in pre-departure data theft.

### How It Happens

Employees set up automatic email forwarding for several reasons: to read work email on a personal device that is not enrolled in the corporate MDM system, to keep a copy of work communications "just in case," to work around corporate email storage limits, or, in the malicious case, to silently copy all incoming and outgoing communications to an external address that persists even after corporate account access is revoked.

Most email platforms (Exchange, Gmail Workspace, Outlook 365) allow users to configure automatic forwarding rules from within the email client settings. Without technical controls preventing this, an employee can set up forwarding in two minutes and all subsequent email, including replies to emails they send, is mirrored to their personal inbox.

### Why It Matters

Corporate email contains some of the most sensitive data in any organisation: strategic plans, personnel decisions, client communications, legal advice, financial projections, and internal conflicts. An employee who forwards all corporate email to a personal account is creating a persistent copy of this data in a system the organisation cannot control, audit, or revoke.

**The pre-departure pattern** is well-documented in insider threat investigations. An employee who is planning to leave, particularly one who is going to a competitor or starting a competing business, sets up email forwarding weeks or months before their departure date. After their corporate access is revoked, the forwarding rule continues to operate (or the personal inbox already contains months of copied communications). They retain customer contacts, project details, pricing information, and strategic plans indefinitely.

**Legal and regulatory exposure** is significant. Corporate email containing customer personal data forwarded to an unsecured personal account is a data protection breach in most jurisdictions. GDPR violations of this nature can result in regulatory investigation and fines. Contracts with clients typically prohibit the handling of client data outside approved systems.

### Detection and Prevention

Email security platforms can detect and alert on new forwarding rules, particularly to external domains. Organisations should configure these alerts, review them regularly, and have a clear policy requiring employees to notify IT of any forwarding rules and obtain approval before setting them up. The policy should be explicit: no automatic forwarding to personal email addresses, for any reason.

When an employee's access is terminated, checking for and removing all forwarding rules should be a mandatory step in the offboarding process.

---

## 9. Vendor and Contractor Access Management
**Threat category:** `third_party`

Third-party vendors, contractors, system integrators, and managed service providers routinely require access to an organisation's systems. This access is necessary for legitimate work but creates a category of risk that is distinct from employee risk, one that requires different controls and heightened vigilance.

### The Scope of Third-Party Risk

The 2013 Target breach, one of the most studied supply chain attacks, originated with credentials stolen from a third-party HVAC vendor who had network access for billing and project management purposes. Those credentials provided a foothold into Target's payment systems. The breach exposed 40 million credit and debit card numbers. The vendor was not a sophisticated attacker; their credentials were simply stolen by criminals who identified them as the weakest link.

Third-party breaches share common characteristics: the vendor has more access than their role requires, access is not time-limited, access credentials are shared among multiple vendor staff, and the access is not actively monitored by the client organisation.

### The Principle of Least Privilege for Vendors

Every vendor should have access to the minimum set of resources required to perform their contracted work, and nothing more. This seems obvious but is routinely violated in practice. Vendor accounts that were provisioned for a specific project three years ago and never revoked are common in most organisations. The vendor staff who originally used those accounts may have left their own organisation, meaning the credentials could be in unknown hands.

Vendor access should be: scoped to specific systems, time-limited (expiring at contract end with a defined renewal process), individually attributed (no shared accounts, each vendor staff member has their own credential), monitored for unusual behaviour, and revoked immediately upon contract termination.

### Recognising Unusual Vendor Behaviour

Employees who work with vendors should be alert to: requests for access beyond the vendor's contracted scope ("while I'm in the system, can you give me access to X as well?"), requests for credentials to be sent via email or messaging rather than through a provisioning system, access at unusual hours or from unusual locations, and resistance to normal access controls and monitoring ("this will work faster if you turn off the firewall rule for now").

These patterns do not necessarily indicate malicious intent, they may reflect a vendor cutting corners for efficiency, but they should be reported to IT and the vendor relationship manager for review.

### Vendor Offboarding

Terminating vendor access at contract end is as important as provisioning it at contract start. Organisations should maintain a register of all active vendor accounts, review it regularly, and have a defined offboarding process that triggers access revocation on contract expiry. Vendors themselves should be contractually obligated to notify the client when staff with access to client systems leave their employment.

---

## 10. Recognising Behavioural Indicators of Malicious Insiders
**Threat category:** `malicious`

Malicious insider incidents rarely emerge without warning. Research from the Carnegie Mellon CERT Insider Threat Center, which has studied hundreds of confirmed insider threat cases, consistently identifies behavioural indicators that preceded the damaging act, often by weeks or months. Recognising these indicators and understanding what to do with them is a critical competence for managers and team leads.

### The Psychology of the Malicious Insider

Most malicious insiders do not arrive at their organisation with harmful intent. The path to damaging behaviour typically begins with a perceived grievance, unfair treatment, a passed-over promotion, a redundancy decision, a disciplinary action, that the individual internalises. Over time, the grievance is reframed in a way that justifies retaliatory action: "The organisation took something from me, so taking this information is fair." This rationalisation process, not sudden impulse, is the normal trajectory.

This matters for detection because the grievance phase, before any harmful action is taken, is often visible to observant colleagues and managers. Intervention at the grievance phase, through constructive management, HR support, or conflict resolution, can prevent escalation to harmful action.

### Behavioural Indicators

The CERT research identifies several categories of observable behaviour that correlate with insider threat activity. These are not diagnostic, they are indicators that warrant attention and follow-up, not accusation.

**Work performance and attitude changes:** Sudden unexplained deterioration in work quality or engagement. Withdrawal from team activities they previously participated in. Expressed resentment toward management, colleagues, or the organisation in meetings or informally. Repeated references to perceived unfair treatment. Disregard for policies they previously followed.

**Digital behaviour changes:** Accessing systems at unusual hours without a business reason. Downloading or copying significantly more data than their role typically requires. Accessing data outside their normal work area, a finance employee accessing HR records, for example. Repeated failed access attempts to systems they are not authorised for. Sending large email attachments to personal email addresses. Searching for sensitive documents they have not previously needed.

**Pre-departure indicators:** These are particularly significant when combined with known or suspected departure plans. Cleaning out personal items from the desk earlier than a formal resignation date. Declining new project assignments or long-term responsibilities. Asking unusual questions about data retention policies or how the organisation handles IP upon departure. Researching competitor companies on corporate devices.

### What To Do

Observing potential behavioural indicators does not mean confronting the individual, conducting your own investigation, or alerting other colleagues. The correct action is to report what you have observed to your manager and/or the HR or security team through the appropriate channel, providing factual observations without interpretation. "I noticed John accessed the server room at 11 PM on three occasions last week" is a useful report. "I think John is stealing data" is not.

Organisations with effective insider threat programmes combine technical monitoring with trained human observation. Neither alone is sufficient. Technology can detect anomalous data access; humans can detect the attitudinal changes that precede it.

---

## 11. Clean Desk Policy and Printed Document Security
**Threat category:** `negligent`

The clean desk policy is frequently dismissed as a minor bureaucratic requirement, but the physical exposure of sensitive information is a genuine and underappreciated risk. Physical documents, exposed screens, and casual conversations overheard in open offices create information exposure that cannot be detected, logged, or reversed.

### What Gets Left Behind

In offices without an enforced clean desk culture, it is common to find: printed HR documents left in printer output trays, personnel files left open on desks overnight, meeting notes from sensitive discussions visible on whiteboards, sticky notes with passwords or access codes adhered to monitors or underneath keyboards, and client documents left in conference rooms after meetings.

Each of these creates an opportunity for anyone who enters the space, a visitor, a cleaning contractor, a colleague from another department, or an attacker who has physically accessed the building, to photograph, read, or remove the document.

### The Printer Output Tray Problem

Shared office printers are among the most consistently overlooked sources of physical information exposure. Employees printing sensitive documents and then attending to something else before collecting the printout leave the document available to anyone who walks past. In busy offices, this happens dozens of times per day. HR reports, payroll documents, legal correspondence, and strategic plans are routinely left in printer trays.

The mitigation is straightforward: use secure print release, where the document is held in the printer's queue and only released when the authorised user presents their badge or enters a PIN at the printer. This is available on most enterprise-grade printers and should be the default for all printing.

### Document Disposal

Confidential documents should be shredded using a cross-cut or micro-cut shredder, not discarded in recycling bins or general waste. Strip-cut shredding (which produces long strips) is inadequate, documents shredded this way have been reassembled by investigators and, in documented cases, by competitive intelligence operatives. Recycling bins in offices should not be used for documents containing any information that would not be published on the company website.

### Video Calls and Screen Visibility

The shift to hybrid working has introduced new physical exposure risks. Home office backgrounds visible in video calls may reveal personal information or, if the employee is working from the office, other employees' screens, whiteboards, or confidential printouts. The practice of blurring or replacing backgrounds should be a default, not an afterthought.

Screens visible to passers-by in open-plan offices or café working environments should use privacy screen filters. Employees who work in public locations should be conscious of shoulder surfing, the act of observing someone's screen in a public space. A security researcher demonstrated that a person reading a newspaper on an airplane could reconstruct the content of a neighbouring passenger's presentation from peripheral vision.

---

## 12. Data Classification – Knowing What You're Handling
**Threat category:** `negligent`

Data classification is the systematic process of organising data according to its sensitivity and the appropriate handling requirements for each level. Without a shared understanding of what data is sensitive and how it should be handled, employees make inconsistent decisions, and inconsistent decisions create gaps that adversaries exploit.

### Why Classification Matters

The fundamental problem that classification solves is decision-making at scale. An organisation may have millions of files, emails, and records. It is impossible to manually review every piece of data before every action. Classification provides a framework: once data is correctly classified, handling rules follow automatically from the classification level.

Without classification, employees guess. Some guess conservatively (treating everything as sensitive, slowing down legitimate work). Most guess liberally (treating everything as shareable because that is the path of least resistance). The liberal guessers create the security incidents.

### Standard Classification Levels

Most organisations use a four-level model:

**Public:** Information that is explicitly approved for external release. Marketing materials, published annual reports, press releases, job postings. There is no restriction on sharing or distribution.

**Internal:** Information for use within the organisation that is not intended for external parties but whose disclosure would cause minimal harm. General internal communications, process documentation, non-sensitive meeting notes.

**Confidential:** Information whose unauthorised disclosure could cause significant harm to the organisation, its clients, or its employees. Customer personal data, employee records, financial projections not yet released, legal correspondence, strategic plans, pricing information, contracts.

**Restricted:** The highest sensitivity level. Information whose disclosure could cause severe harm: trade secrets, board-level communications, merger and acquisition plans, encryption keys, system architecture for critical infrastructure, law enforcement-sensitive information.

### Handling Rules by Level

Classification only creates value if handling rules are understood and followed. Typical rules across common actions:

For **Confidential** data: encrypt before emailing, do not send to personal email addresses, do not store in personal cloud storage, do not discuss in public locations, shred rather than recycle when printed.

For **Restricted** data: email only with explicit approval and encryption, store only in designated systems, access by named individuals with specific authorisation, no printing without approval, immediate reporting if potentially exposed.

### Common Misclassification Scenarios

**Underclassification** is more common and more dangerous. Sending a client database as an email attachment marked Internal. Storing payroll data in a shared drive that all staff can access. Discussing merger plans in a meeting room with glass walls.

**Overclassification** slows legitimate work and, paradoxically, leads to classification fatigue, where employees begin to ignore classifications entirely because everything is marked the same level regardless of actual sensitivity.

---

## 13. Privilege Escalation and the Least-Privilege Principle
**Threat category:** `malicious`

Access control is the technical mechanism by which an organisation defines who can do what to which data and systems. The principle of least privilege, giving each user the minimum access required for their role, and nothing more, is the foundational concept of access control design. Its violation is a consistent theme in the most damaging insider threat incidents on record.

### What Privilege Escalation Means

Privilege escalation is the process by which an attacker or insider gains a higher level of access than they are supposed to have. There are two forms:

**Vertical escalation:** A standard user gaining administrator-level access. This could be achieved by exploiting a software vulnerability, by stealing an administrator's credentials, or, in the insider case, by having been granted administrator access that was never revoked.

**Horizontal escalation:** Accessing data or systems belonging to a peer with the same privilege level but a different scope. A financial analyst accessing HR records, or a junior developer accessing production databases they have no development need for.

### Privilege Creep: How It Happens

Privilege creep is the gradual accumulation of access rights over time, driven by legitimate short-term needs that were never rescinded. An employee who temporarily covered for a colleague on medical leave was given that colleague's system access, and the access was never removed. An employee who moved from one department to another retained all the access from their previous role in addition to gaining the new role's access.

In organisations without regular access reviews, privilege creep is universal. Studies of access control posture in enterprises consistently find that a significant proportion of active accounts have access far beyond what the role requires, and a proportion of active accounts belong to employees who have left.

### Why Excessive Privilege is Dangerous

The degree of damage an insider can cause is directly proportional to the access they hold. An administrator-level account can: read and copy all data across all systems, modify or delete audit logs (covering their tracks), create new accounts, disable security controls, and encrypt systems for ransomware purposes. A user-level account can do none of these things without first escalating privilege.

This is not merely a theoretical concern. Edward Snowden, working as a contractor for a government agency, used a system administrator account, access far beyond what a contractor in his role should have had, to access and exfiltrate classified documents across multiple agency systems. The excessive access was a failure of least-privilege enforcement.

### Access Reviews and Recertification

The operational mechanism for enforcing least privilege over time is the periodic access review, also called access recertification. Managers should regularly confirm, for each member of their team, that the access those team members hold is appropriate for their current role. Access that cannot be justified should be removed.

---

## 14. Incident Reporting Culture – Speak Up Without Fear
**Threat category:** `all`

Every security incident that was successfully contained had one thing in common: someone reported it quickly. Every incident that caused catastrophic damage had another thing in common: the problem was known, or suspected, before it became critical, and no one reported it. The difference between a contained breach and a front-page breach is frequently not the sophistication of the attack but the speed of reporting.

### Why People Don't Report

Research into reporting behaviour identifies several consistent barriers. **Fear of blame** is the most common. An employee who clicked a phishing link fears that reporting it will result in disciplinary action, ridicule, or termination. This fear is often disproportionate to the actual consequence, most security teams treat reporting as a positive act, regardless of the triggering event, but it is real and powerful enough to delay or prevent reporting in a majority of cases.

**Uncertainty about whether something is worth reporting** is the second most common barrier. "I'm probably overreacting." "It's probably nothing." "I don't want to waste the security team's time." This uncertainty is resolved by establishing a clear, low-friction reporting mechanism and explicitly stating that there is no penalty for false positives, reporting something that turns out to be harmless is always the right decision.

**Not knowing how to report** is a surprisingly common barrier in organisations where the reporting mechanism is not prominently communicated. If an employee has to search for how to report a security incident, many will not bother.

### The Cost of Delayed Reporting

The dwell time of a breach, the period between initial compromise and detection, averages hundreds of days in organisations without effective reporting culture. During that time, the attacker is expanding access, exfiltrating data, and establishing persistence. Every additional day of undetected presence increases the scope of the breach.

In contrast, a phishing click that is reported within minutes can be triaged before the malicious payload executes, before the attacker uses the harvested credentials, and before any data leaves the organisation. The window of action is narrow; reporting speed is the variable that determines whether it is used.

### Building a Reporting Culture

The behaviours of leadership determine the culture of reporting. When a senior leader publicly thanks an employee for reporting a security incident, regardless of whether that employee was the one who clicked the phishing link, they signal that reporting is valued and safe. When the opposite happens, employees learn quickly that reporting carries risk.

Reporting mechanisms should be: visible (prominently displayed), simple (one click, one call, one email), and fast-responding (acknowledgement within an appropriate timeframe reassures the reporter that their report was received and acted upon).

---

## 15. Remote Work Security – Home Networks and Public Wi-Fi
**Threat category:** `negligent`

The expansion of remote and hybrid working has extended the organisational perimeter to hundreds of individual home networks and public hotspots, each with its own security posture, each outside the organisation's direct control. The attack surface for corporate data has grown dramatically; the security controls protecting that surface have not kept pace.

### Home Network Risks

The home router is the gateway between a home network and the internet. Most home routers are configured by internet service providers with default settings, default administrative credentials, and infrequent firmware updates. Research consistently finds that a significant proportion of home routers in use have known, unpatched vulnerabilities in their firmware.

An attacker who compromises a home router has a position to conduct man-in-the-middle attacks (intercepting traffic between the device and the internet), redirect traffic to malicious sites, or pivot to attack other devices on the network. A compromised home router on a network where an employee is accessing corporate systems is a serious threat.

The mitigations are accessible: change the default administrative password on the home router, ensure the router firmware is updated (check the manufacturer's website or the router's admin panel), use WPA3 or WPA2 encryption for Wi-Fi, and use the organisation's VPN for all corporate system access regardless of where you are working.

### Public Wi-Fi Risks

Public Wi-Fi networks in hotels, airports, cafés, and conference centres are high-risk environments for corporate data. The risks include: evil twin attacks (a rogue access point with a name similar to the legitimate network, such as "Airport Free WiFi" vs "Airport_Free_WiFi", connecting to the rogue network allows the attacker to intercept all traffic), unencrypted networks (traffic sent over unencrypted Wi-Fi can be read by anyone on the same network with readily available tools), and network-level attacks against other connected devices.

The rule is simple: use a corporate VPN for all work activity on any network you do not control. The VPN encrypts all traffic from the device to the corporate gateway, making interception by a rogue access point or a network-level attacker ineffective.

### Device and Session Management

Remote work creates additional risks around device security and session management. Devices should auto-lock after a short period of inactivity, a laptop left unlocked in a café while the employee retrieves their order is an exposure. Corporate devices should not be shared with family members, even for benign uses, because family members may inadvertently install software, browse to malicious sites, or expose corporate data through their activity.

Work sessions should be conducted with awareness of the physical environment. Video calls in public places may be overheard. Documents open on a laptop screen may be visible to people nearby. Business discussions in airport lounges are routinely overheard by competitors.

---

## 16. Intellectual Property Theft Before Resignation
**Threat category:** `malicious`

The period immediately before an employee's departure is statistically the highest-risk period for insider data theft. Research from Securonix and other security firms consistently shows a spike in anomalous data access and exfiltration activity in the 30-60 days before an employee's resignation or termination. The pattern is predictable enough to be a standard detection use case in insider threat monitoring programmes.

### Why It Happens

Employees who are leaving for a competitor or starting a competing business often rationalise taking organisational data in several ways. They may view their accumulated knowledge and work product as personally owned, "I created this, so it belongs to me." They may believe that general knowledge, skills, and experience are indistinguishable from specific confidential information, conflating the two to justify copying specific client lists, product roadmaps, or source code. They may view the organisation as having wronged them in some way, providing emotional justification for taking something of value.

In many jurisdictions, employment contracts and trade secret law are clear: work product created during employment belongs to the employer, and taking it constitutes theft of intellectual property. The rationalisation is not legally valid, but it is psychologically real.

### Common Exfiltration Methods

Departing employees use a range of methods to remove data. **Email to personal accounts** is the most common and most easily detected, sending batches of files, forwarding client contact lists, emailing proprietary documents to personal Gmail or similar accounts. **USB drives** are used for bulk copying without network traces. **Personal cloud storage sync**, if a personal Dropbox or Google Drive has been connected to the work computer, can automatically sync files the employee copies there. **Screenshots and photographs** of screens are low-tech but effective for capturing specific pieces of information.

The types of data most commonly taken: customer lists and contact information, pricing information and commercial terms, product roadmaps and design documents, source code, financial models and projections, and proposal templates and sales collateral.

### Technical Detection

Modern endpoint detection and response (EDR) and data loss prevention (DLP) tools can detect anomalous file access and copy behaviour. Alerts should be configured for: unusually large volumes of files being accessed or copied, large email attachments sent to non-corporate domains, USB drive insertions and the volume of data copied to them, and cloud sync activity to personal storage services.

Access logs also reveal behavioural changes: an employee who has never accessed the HR shared drive suddenly accessing it, or one who has not logged in outside business hours suddenly working at midnight.

### Offboarding Controls

Effective offboarding is the primary preventive control. Access should be revoked promptly upon notification of departure, ideally simultaneously with the employee being notified of termination, or on their last day for voluntary departures. The window between an employee knowing they are leaving and their access being revoked is the highest-risk window.

---

## 17. Business Email Compromise (BEC) and CEO Fraud
**Threat category:** `compromised`

Business Email Compromise is one of the most financially damaging categories of cybercrime. The FBI Internet Crime Complaint Center reported BEC losses exceeding $2.9 billion in 2023 alone, more than any other category of internet crime. Unlike ransomware, BEC rarely involves malware; it is a pure social engineering attack that exploits trust in email as a communication medium.

### How BEC Works

In its simplest form, a BEC attack involves sending a fraudulent email that appears to come from a trusted source, a senior executive, a known supplier, a legal counsel, requesting a financial action: a wire transfer, a change of payment details, the purchase of gift cards, or the disclosure of sensitive information.

The attacker creates the appearance of legitimacy through several methods. **Domain spoofing** involves using a domain that is visually similar to the legitimate one (company-name.co vs company-name.com). **Display name spoofing** involves setting the sender display name to a real executive's name while the actual address is controlled by the attacker. **Compromised accounts**, where the attacker has actually gained access to a legitimate email account, are the most dangerous form, because all the technical indicators that security tools check (domain, DKIM, SPF) are genuine.

### The CEO Fraud Pattern

CEO fraud is the most common BEC variant. The attacker poses as the Chief Executive Officer (or another senior leader) and emails a financial employee, typically the CFO, controller, or accounts payable, requesting an urgent wire transfer to a new account, often citing a confidential acquisition, a regulatory matter, or a supplier payment that requires immediate action.

Several psychological elements make this effective: **authority** (the CEO is not questioned), **urgency** (there is a deadline that precludes following normal process), **confidentiality** (the employee is told not to discuss it with anyone, preventing the peer verification that would reveal the fraud), and **plausibility** (the request references a real business context gathered from OSINT).

### Vendor Payment Fraud

In the vendor payment variant, the attacker poses as a known supplier and notifies the accounts payable department that banking details have changed. Subsequent payments are redirected to an attacker-controlled account. The fraud may go undetected for weeks, until the real supplier queries a missed payment.

### Verification Protocols

The defence against BEC is mandatory verification of any financial request received by email, regardless of the apparent sender. The verification must use a communication channel that is independent of email: call the requestor on a phone number from the company directory (not a number in the email), walk to their office, or use the official supplier contact details already on file.

Any request that discourages verification ("this is confidential, don't call me directly, just process it") should be treated as an immediate red flag.

---

## 18. Supply Chain and Third-Party Software Risk
**Threat category:** `third_party`

A supply chain attack targets an organisation indirectly, by compromising a vendor, supplier, or partner whose software, services, or access the organisation trusts. The attacker uses the trusted third party as a vehicle to reach targets that would otherwise be hardened against direct attack. Supply chain attacks have grown dramatically in frequency and impact because they allow a single compromise to propagate to hundreds or thousands of downstream organisations simultaneously.

### The SolarWinds Incident

The SolarWinds attack, discovered in December 2020, remains the defining example of software supply chain compromise. Attackers (subsequently attributed to Russian state intelligence) inserted malicious code into the build process of SolarWinds' Orion network management software. The malicious update was code-signed and distributed through SolarWinds' legitimate update infrastructure. Approximately 18,000 organisations downloaded and installed the compromised update. Among those were multiple US government departments and major technology companies. The attackers had persistent, stealthy access to these organisations for months before detection.

The attack was devastating precisely because it exploited trust. The organisations that installed the update were following best practice, they were installing signed updates from a trusted vendor through the normal software update process. There was no obvious red flag.

### The Mechanics of Build Pipeline Compromise

Software is not written and shipped directly to end users. It passes through a build pipeline: source code is compiled, tested, packaged, signed, and distributed. Any step in this pipeline is a potential compromise point. Attackers who gain access to a vendor's build environment can insert malicious code before the software is compiled, meaning the malicious code is included in the final product even though the source code appears clean.

This is why software supply chain security is a technical and organisational challenge for vendors, not just end users. However, end users and procurement teams can take steps to reduce exposure.

### Third-Party Software Risk for End Users

Employees who install software, including browser extensions, desktop utilities, developer tools, and productivity applications, are introducing third-party code into the organisation's environment. Each piece of installed software is a potential supply chain risk. The mitigations: install only software approved through the IT procurement process, do not install software from unofficial sources or in response to prompts on websites, keep all software updated through official channels, and report any software that prompts for unusual permissions or behaves unexpectedly.

Browser extensions deserve particular attention. A browser extension runs with elevated privileges, it can read the content of every page you visit, including pages where you enter credentials or view sensitive data. Extensions are frequently updated by developers (or by attackers who have purchased or compromised an extension), meaning an extension that was safe when installed may become malicious after an update.

---

## 19. Monitoring, Audit Logs, and Employee Privacy
**Threat category:** `all`

Organisational security monitoring is a topic that generates discomfort when it is not communicated transparently. Employees who feel surveilled without understanding why or what is monitored are more likely to work around security controls, report security concerns less willingly, and view the security function as adversarial. Transparent communication about monitoring, what it covers, why it exists, how the data is used, and what protections apply, converts monitoring from a source of tension to a shared security tool.

### What Monitoring Exists and Why

Organisations typically monitor at several levels. **Network monitoring** captures the metadata of network connections, what systems are accessed, when, and in what volume, without necessarily reading the content of encrypted communications. This is used to detect anomalous access patterns, data exfiltration volumes, and connections to known-malicious infrastructure.

**Email monitoring** in corporate environments may include content scanning for data loss prevention purposes, detecting when documents containing sensitive data patterns (credit card numbers, personal data fields, confidential project names) are being sent outside the organisation. Most email security platforms scan for malicious attachments and links on inbound email.

**Endpoint monitoring** via EDR (endpoint detection and response) tools tracks process execution, file access, USB insertions, and other system events on corporate devices. This provides forensic capability in incident investigations and can alert on anomalous behaviour in real time.

**Access logs** record every authentication event, who logged in to which system, when, from where, and whether the attempt was successful.

### What Is and Is Not Monitored

Corporate devices and corporate accounts are monitored. Personal devices on personal networks, personal email accounts, and personal browsing on personal devices are not. This boundary matters and should be clearly communicated. Employees who conduct personal business on corporate devices should understand that those activities may be visible to security systems.

### How Monitoring Data Is Used

Monitoring data is used for: detecting and responding to security incidents, investigating suspected policy violations, meeting regulatory obligations (many industries require audit trails of data access), and forensic investigation after a breach. It is not used for real-time surveillance of employee productivity, monitoring personal communications sent through personal accounts, or generating reports on individual employee behaviour in the absence of a specific security concern.

### Audit Logs as an Exoneration Tool

Security monitoring data has frequently been used to exonerate employees wrongly suspected of policy violations or security incidents. When an investigation begins, the audit log is the first source of factual information. Employees who follow policy and behave consistently have nothing to fear from audit logs, the log will show exactly what they did and when.

---

## 20. AI Tools and Data Leakage Risk
**Threat category:** `negligent`

Generative AI tools, large language models accessible through web interfaces, have been rapidly adopted across organisations for productivity tasks: drafting documents, writing code, summarising reports, analysing data. The productivity gains are real. So are the data security risks, which are less well-understood by most users.

### How Public AI Services Handle Data

When an employee types a prompt into a public generative AI service, that text is transmitted to the service provider's servers and processed there. The data leaves the corporate environment. Depending on the service's terms of service and privacy policy, that data may be: stored and used to train or fine-tune future versions of the model, reviewed by human annotators employed by or contracted to the service provider, retained for a period defined by the provider's data retention policy, or subject to the provider's jurisdiction's law enforcement access procedures.

Users who paste sensitive data into public AI chat interfaces are effectively sending that data to a third party with no data processing agreement, no deletion guarantee, and no visibility into how it is stored or who may access it. The productivity benefit is immediate and visible; the data exposure is invisible and may not manifest as a breach for months or years.

### High-Risk Use Cases

Specific employee behaviours that create significant data risk: pasting source code containing proprietary algorithms, APIs, or credentials into a code-generation tool; entering customer names, email addresses, or financial details into a summarisation tool; uploading confidential documents for AI analysis; describing unreleased products, strategic plans, or acquisition targets in prompts; and using AI to draft communications that reference confidential client matters.

The Samsung incident (2023) illustrated this concretely. Samsung employees pasted proprietary semiconductor code into ChatGPT on three separate occasions, one to fix a bug in source code, one to optimise code for a meeting note system, and one to summarise a confidential meeting, before the company had established AI usage policies or technical controls. Samsung subsequently banned ChatGPT on corporate devices.

### Approved AI Use

The appropriate response to AI adoption risk is not prohibition, it is governance. Organisations should: establish a clear policy on which AI tools are approved for which data types, procure enterprise versions of AI tools that include contractual data isolation and privacy commitments, provide a designated channel for employees to request AI tool assessments, and train employees to self-classify the sensitivity of data before deciding whether to use an AI tool.

Enterprise AI agreements typically include commitments that customer data will not be used for model training, that data will be deleted after a defined retention period, and that data is processed in a specified jurisdiction under defined security standards. These commitments do not exist for free consumer-tier AI services.

### The Credential Risk

A separate but critical risk: AI coding assistants used for development tasks may generate code suggestions that include example credentials, or may inadvertently expose credentials present in code snippets pasted into the tool. Developers should never paste code containing real credentials, API keys, or connection strings into any AI tool. Secrets management practices, storing credentials in environment variables or secrets vaults, never in code, reduce this risk substantially.

---

*Content library version 1.0, June 2026*
*All content is intended for internal use and adaptation by the Guardian platform administrator.*
