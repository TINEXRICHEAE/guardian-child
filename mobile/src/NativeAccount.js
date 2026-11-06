import React, { useState } from 'react';
import { Alert, Image, ScrollView, Text, TextInput, View } from 'react-native';
import * as DocumentPicker from 'expo-document-picker';
import { Button } from './NativePage';

export default function NativeAccount({ profile, client, palette, onClose, onRefresh, onSecurity, onDeleted }) {
  const [name, setName] = useState(profile.full_name || ''), [phone, setPhone] = useState(profile.phonenumber || '');
  const [busy, setBusy] = useState(false), [error, setError] = useState(null);
  async function run(action) {
    setBusy(true); setError(null);
    try { await action(); await onRefresh(); } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function picture() {
    const result = await DocumentPicker.getDocumentAsync({ type: 'image/*', copyToCacheDirectory: true });
    if (result.canceled) return;
    const f = result.assets[0];
    if (f.size > 5 * 1024 * 1024) throw new Error('Choose an image smaller than 5 MB.');
    const data = new FormData(); data.append('profile_picture', { uri: f.uri, name: f.name, type: f.mimeType || 'image/jpeg' });
    await client.account('picture', data, true);
  }
  const input = { borderWidth: 1, borderColor: palette.line, color: palette.text, padding: 15, borderRadius: 12, fontSize: 16 };
  return <ScrollView contentContainerStyle={{ padding: 24, gap: 16 }} keyboardShouldPersistTaps="handled">
    <Text style={{ color: palette.text, fontSize: 30, fontWeight: '800' }}>Your account</Text>
    <Text selectable style={{ color: palette.muted }}>{profile.email}</Text>
    {error && <Text accessibilityRole="alert" style={{ color: palette.error }}>{error}</Text>}
    {profile.avatar_url && <Image source={{ uri: profile.avatar_url }} style={{ width: 90, height: 90, borderRadius: 45 }} />}
    <Button title="Choose profile picture" palette={palette} secondary disabled={busy} onPress={() => run(picture)} />
    <Text style={{ color: palette.text }}>Full name</Text><TextInput accessibilityLabel="Full name" style={input} value={name} onChangeText={setName} />
    <Text style={{ color: palette.text }}>Phone number</Text><TextInput accessibilityLabel="Phone number" keyboardType="phone-pad" style={input} value={phone} onChangeText={setPhone} />
    <Button title="Save profile" palette={palette} disabled={busy} onPress={() => run(async () => { await client.account('profile', { full_name: name, phonenumber: phone }); Alert.alert('Guardian', 'Profile saved.'); })} />
    <Button title="Password and security" palette={palette} secondary onPress={onSecurity} />
    <Button title="Deactivate account" palette={palette} secondary disabled={busy} onPress={() => Alert.alert('Deactivate your account?', 'This will deactivate your Guardian account and sign you out.', [{ text: 'Cancel', style: 'cancel' }, { text: 'Deactivate', style: 'destructive', onPress: () => run(async () => { await client.account('account/delete', {}); onDeleted(); }) }])} />
    <Button title="Close" palette={palette} secondary onPress={onClose} />
  </ScrollView>;
}
