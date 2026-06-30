const fs = require('fs');
const path = require('path');

const BASE_URL = 'http://localhost:8000/api/v1';

const USERS = {
  admin: { email: 'admin@docuquery.ai', password: 'password123' },
  manager: { email: 'manager@docuquery.ai', password: 'password123' },
  employee: { email: 'employee@docuquery.ai', password: 'password123' },
};

const tokens = {};

async function login(role) {
  const res = await fetch(`${BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: USERS[role].email, password: USERS[role].password })
  });

  if (!res.ok) throw new Error(`Login failed for ${role}: ${await res.text()}`);
  const data = await res.json();
  tokens[role] = data.access_token;
  console.log(`✅ Logged in as ${role}`);
}

async function uploadRestrictedDoc() {
  const content = "Project X is a new stealth project launching in 2027. The budget is $50M. Only admins know about this.";
  
  // Using native fetch FormData in Node.js 18+ requires the file to be a Blob
  const blob = new Blob([content], { type: 'text/plain' });
  const formData = new FormData();
  formData.append('file', blob, 'SuperSecretPlans.txt');
  formData.append('title', 'Super Secret Plans');
  formData.append('access_level', 'restricted');

  const res = await fetch(`${BASE_URL}/documents/upload`, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${tokens.admin}` },
    body: formData
  });

  if (!res.ok) throw new Error(`Upload failed: ${await res.text()}`);
  console.log(`✅ Admin uploaded restricted document 'SuperSecretPlans.txt'`);
}

async function query(role, question) {
  console.log(`\n--- ${role.toUpperCase()} querying: '${question}' ---`);
  const res = await fetch(`${BASE_URL}/query`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${tokens[role]}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ question: question })
  });

  if (!res.ok) throw new Error(`Query failed: ${await res.text()}`);
  const data = await res.json();
  console.log(`Answer: ${data.answer}`);
  console.log('Sources:');
  data.sources.forEach(src => {
    console.log(`  - ${src.document_title} (Relevance: ${src.relevance_score.toFixed(2)})`);
  });
  return data;
}

async function verifyAdminDashboard() {
  console.log('\n--- Testing Admin Endpoints ---');
  
  const usersRes = await fetch(`${BASE_URL}/admin/users`, {
    headers: { 'Authorization': `Bearer ${tokens.admin}` }
  });
  if (!usersRes.ok) throw new Error('Failed to fetch users');
  const users = await usersRes.json();
  console.log(`✅ Admin users endpoint working (found ${users.length} users)`);

  const metricsRes = await fetch(`${BASE_URL}/admin/metrics`, {
    headers: { 'Authorization': `Bearer ${tokens.admin}` }
  });
  if (!metricsRes.ok) throw new Error('Failed to fetch metrics');
  const metrics = await metricsRes.json();
  console.log(`✅ Admin metrics endpoint working`);
  console.log(`   Total Queries: ${metrics.total_queries_30d}`);
  console.log(`   Total Documents: ${metrics.total_documents}`);
}

async function runTests() {
  try {
    for (const role of Object.keys(USERS)) {
      await login(role);
    }

    // Skipping upload, seed script already generated docs.

    // Wait for async processing (chunking/embedding)
    await new Promise(r => setTimeout(r, 2000));

    // Admin should see it
    const adminData = await query('admin', 'What is Project X and what is the budget?');
    const adminSawIt = adminData.sources.some(s => s.document_title === 'Super Secret Plans');
    if (!adminSawIt) throw new Error("Admin didn't get the restricted source!");
    console.log("✅ Verified: Admin has access to restricted content.");

    // Employee should NOT see it
    const empData = await query('employee', 'What is Project X and what is the budget?');
    const empSawIt = empData.sources.some(s => s.document_title === 'Super Secret Plans');
    if (empSawIt) throw new Error("SECURITY FLAW: Employee saw restricted source!");
    console.log("✅ Verified: Employee cannot see restricted content.");

    await verifyAdminDashboard();

    console.log('\n🎉 All RBAC and Admin tests passed successfully!');
  } catch (err) {
    console.error('Test failed:', err);
  }
}

runTests();
