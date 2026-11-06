import React, { useState } from 'react';
import { Alert, Image, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import * as DocumentPicker from 'expo-document-picker';
import * as ImagePicker from 'expo-image-picker';
import { all, text, initialValues, validate, parsePage, controls } from './pageModel';

const skip = new Set(['script', 'style', 'svg', 'head', 'footer', 'nav', 'noscript', 'template']);
const attrs = (n) => n.attribs || {};
const children = (n) => n.children || [];
export default function NativePage({ page, onNavigate, onSubmit, busy, palette }) {
  function render(node, key, form) {
    if (node.type === 'text') return node.data.trim() ? <Text key={key} selectable style={{ color: palette.text, lineHeight: 23 }}>{node.data.trim()}</Text> : null;
    const a = attrs(node), name = node.name;
    if (!name || skip.has(name) || a['aria-hidden'] === 'true' || a.id?.match(/Loader|Spinner|previewBox|darkToggle|messageBox|toast|rejectReasonModal/i)) return null;
    if (name === 'form') return <NativeForm key={key} node={node} page={page} render={render} onSubmit={onSubmit} busy={busy} palette={palette} />;
    if (['input', 'textarea', 'select'].includes(name)) return form?.field(node, key) || null;
    if (name === 'button') {
      if (a.onclick?.includes('window.print')) return <Button key={key} title="Open printable report" palette={palette} secondary onPress={() => Alert.alert('Print or export', 'Open this report in your browser to print or save it as PDF. Use the open icon in the header.')} />;
      if (!form) return null;
      if (a.type === 'button') return a['data-example'] ? <Button key={key} title={text(node)} onPress={() => form?.setValue('content', a['data-example'])} palette={palette} secondary /> : null;
      return <Button key={key} title={text(node) || a.value || 'Continue'} disabled={busy || 'disabled' in a} onPress={() => form?.submit(a)} palette={palette} />;
    }
    if (name === 'a') {
      if (!a.href || a.href.startsWith('#') || a.href.startsWith('javascript:')) return null;
      return <Pressable key={key} accessibilityRole="link" onPress={() => onNavigate(a.href)} style={[s.link, { borderColor: palette.line }]}>
        {children(node).map((n, i) => render(n, `${key}.${i}`, form))}<Text style={{ color: palette.accent, alignSelf: 'flex-end' }}>→</Text>
      </Pressable>;
    }
    if (name === 'img') return a.src && !a.src.startsWith('data:') ? <Image key={key} accessibilityLabel={a.alt} source={{ uri: new URL(a.src, page.url).href }} style={s.image} resizeMode="contain" /> : null;
    if (name === 'iframe') return a.srcdoc ? <View key={key} style={s.card}>{parsePage(a.srcdoc).nodes.map((n, i) => render(n, `${key}.${i}`, form))}</View> : a.src ? <Button key={key} title={a.title || 'Open document'} palette={palette} secondary onPress={() => onNavigate(a.src)} /> : null;
    if (name === 'canvas') return <Text key={key} style={{ color: palette.muted }}>Chart available in the browser. See the figures and tables on this page.</Text>;
    if (name === 'table') return <ScrollView key={key} horizontal style={s.table}><View>{children(node).map((n, i) => render(n, `${key}.${i}`, form))}</View></ScrollView>;
    if (name === 'tr') return <View key={key} style={[s.row, { borderBottomWidth: 1, borderColor: palette.line }]}>{children(node).map((n, i) => render(n, `${key}.${i}`, form))}</View>;
    if (['td', 'th'].includes(name)) return <View key={key} style={s.cell}>{children(node).map((n, i) => render(n, `${key}.${i}`, form))}</View>;
    if (name === 'label' && form) {
      const input = all(node, (n) => ['input', 'select', 'textarea'].includes(n.name))[0];
      if (input && ['radio', 'checkbox', 'file'].includes(attrs(input).type)) return form.field(input, key, text(node));
    }
    if (/^h[1-6]$/.test(name)) return <Text key={key} accessibilityRole="header" selectable style={[s.heading, { color: palette.text, fontSize: name === 'h1' ? 29 : name === 'h2' ? 23 : 18 }]}>{text(node)}</Text>;
    if (['span', 'strong', 'b', 'em', 'i', 'small', 'code', 'p', 'legend', 'label'].includes(name) && !all(node, (n) => ['a', 'input', 'button', 'select', 'textarea'].includes(n.name)).length) {
      return text(node) ? <Text key={key} selectable style={[s.paragraph, { color: a.class?.includes('text-error') ? palette.error : palette.text }, ['strong', 'legend'].includes(name) ? { fontWeight: '700' } : null]}>{text(node)}</Text> : null;
    }
    const card = name === 'section' || /\bbg-white\b/.test(a.class || '');
    return <View key={key} style={card ? [s.card, { backgroundColor: palette.card, borderColor: palette.line }] : s.group}>
      {name === 'li' && <Text style={{ color: palette.accent }}>•</Text>}{children(node).map((n, i) => render(n, `${key}.${i}`, form))}
    </View>;
  }
  return <View style={s.page}>{page.nodes.map((node, i) => render(node, String(i)))}</View>;
}
function NativeForm({ node, page, render, onSubmit, busy, palette }) {
  const [values, setValues] = useState(() => initialValues(node));
  const [error, setError] = useState(null);
  const setValue = (key, value) => setValues((v) => ({ ...v, [key]: value }));
  async function chooseFile(a, camera = false) {
    try {
      if (camera) {
        if (!(await ImagePicker.requestCameraPermissionsAsync()).granted) { setError('Allow camera access in Android settings to take a photo.'); return; }
        const result = await ImagePicker.launchCameraAsync({ quality: 0.85 });
        if (result.canceled) return;
        const image = result.assets[0];
        setValue(a.name, { uri: image.uri, name: image.fileName || 'photo.jpg', type: image.mimeType || 'image/jpeg' });
      } else {
        const result = await DocumentPicker.getDocumentAsync({ type: a.accept?.startsWith('image') ? 'image/*' : '*/*', copyToCacheDirectory: true });
        if (result.canceled) return;
        const file = result.assets[0];
        if (a.name === 'screenshot' && file.size > 5 * 1024 * 1024) { setError('Choose a screenshot smaller than 5 MB.'); return; }
        setValue(a.name, { uri: file.uri, name: file.name, type: file.mimeType || 'application/octet-stream' });
      }
    } catch (e) { setError(e.message); }
  }
  async function submit(a = {}) {
    const problem = validate(node, values);
    if (problem) { setError(problem); return; }
    const execute = async () => { setError(null); try { await onSubmit(node, values, a); } catch (e) { setError(e.message); } };
    const confirmation = attrs(node).onsubmit?.match(/confirm\(['"](.*?)['"]\)/)?.[1]
      || (/\/(delete|remove|send|approve)\//.test(attrs(node).action || '') ? 'Continue with this action? This updates the records on your Guardian server.' : null);
    if (confirmation) Alert.alert('Confirm action', confirmation, [{ text: 'Cancel', style: 'cancel' }, { text: 'Continue', onPress: execute }]);
    else await execute();
  }
  function field(input, key, wrappedLabel) {
    const a = attrs(input);
    if (!a.name) return null;
    if (a.type === 'hidden' && a.name === 'source_type') return field({ name: 'select', attribs: { name: a.name, 'aria-label': 'Source type' }, children: ['url', 'document', 'prompt'].map((v) => ({ name: 'option', attribs: { value: v }, children: [{ type: 'text', data: v }] })) }, key);
    if (a.type === 'hidden' && a.name === 'reject_reason') return field({ name: 'textarea', attribs: { name: a.name, 'aria-label': 'Rejection reason (optional)' } }, key);
    if (a.type === 'hidden') return null;
    const label = wrappedLabel || page.labels[a.id] || a['aria-label'] || a.placeholder || a.name.replace(/_/g, ' ');
    const disabled = 'disabled' in a || busy;
    if (a.type === 'submit') return <Button key={key} title={a.value || 'Continue'} disabled={disabled} palette={palette} onPress={() => submit(a)} />;
    if (['radio', 'checkbox'].includes(a.type)) {
      const checked = a.type === 'checkbox' ? (values[a.name] || []).includes(a.value || 'on') : values[a.name] === (a.value || 'on');
      const toggle = () => setValue(a.name, a.type === 'checkbox' ? checked ? values[a.name].filter((v) => v !== (a.value || 'on')) : [...(values[a.name] || []), a.value || 'on'] : a.value || 'on');
      return <Pressable key={key} disabled={disabled} onPress={toggle} accessibilityRole={a.type} accessibilityState={{ checked, disabled }} style={s.choice}>
        <Text style={{ color: checked ? palette.accent : palette.muted, fontSize: 25 }}>{a.type === 'radio' ? checked ? '◉' : '○' : checked ? '☑' : '☐'}</Text><Text style={[s.choiceText, { color: palette.text }]}>{label}</Text>
      </Pressable>;
    }
    if (a.type === 'file') return <View key={key} style={s.group}>
      <Button title={values[a.name]?.name || label || 'Choose a file'} palette={palette} secondary disabled={disabled} onPress={() => chooseFile(a)} />
      {a.accept?.startsWith('image') && <Button title="Take a photo" palette={palette} secondary disabled={disabled} onPress={() => chooseFile(a, true)} />}
      {values[a.name] && <Button title="Remove attachment" palette={palette} secondary onPress={() => setValue(a.name, null)} />}
    </View>;
    if (input.name === 'select') return <View key={key} style={s.group}><Text style={{ color: palette.muted }}>{label}</Text>
      {all(input, (n) => n.name === 'option').map((option, i) => {
        const value = attrs(option).value ?? text(option), multiple = 'multiple' in a;
        const selected = multiple ? (values[a.name] || []).includes(value) : values[a.name] === value;
        return <Pressable key={i} disabled={disabled || 'disabled' in attrs(option)} onPress={() => setValue(a.name, multiple ? selected ? values[a.name].filter((v) => v !== value) : [...(values[a.name] || []), value] : value)} style={[s.option, { borderColor: selected ? palette.accent : palette.line, backgroundColor: selected ? palette.selected : palette.card }]}><Text style={{ color: palette.text }}>{selected ? '● ' : '○ '}{text(option)}</Text></Pressable>;
      })}</View>;
    return <View key={key} style={s.group}><Text style={[s.label, { color: palette.muted }]}>{label}{'required' in a ? ' *' : ''}</Text>
      <TextInput accessibilityLabel={label} editable={!disabled && !('readonly' in a)} value={String(values[a.name] ?? '')} onChangeText={(value) => setValue(a.name, value)} placeholder={a.placeholder} placeholderTextColor={palette.muted} secureTextEntry={a.type === 'password'} autoCapitalize="none" autoCorrect={false}
        keyboardType={a.type === 'email' ? 'email-address' : a.type === 'number' ? 'numeric' : a.type === 'tel' ? 'phone-pad' : 'default'} multiline={input.name === 'textarea'} maxLength={a.maxlength ? Number(a.maxlength) : undefined}
        style={[s.input, { color: palette.text, backgroundColor: palette.card, borderColor: palette.line }, input.name === 'textarea' ? { minHeight: 140, textAlignVertical: 'top' } : null]} />
    </View>;
  }
  const hasSubmit = controls(node).some((n) => n.name === 'button' && attrs(n).type !== 'button' || attrs(n).type === 'submit');
  return <View style={[s.form, { borderColor: palette.line }]}>{error && <Text accessibilityRole="alert" style={{ color: palette.error }}>{error}</Text>}{children(node).map((n, i) => render(n, `form.${i}`, { field, submit, setValue }))}
    {!hasSubmit && <Button title={(attrs(node).id || 'Submit').replace(/Form$/, '').replace(/([A-Z])/g, ' $1')} palette={palette} disabled={busy} onPress={() => submit()} />}
  </View>;
}
export function Button({ title, onPress, palette, secondary, disabled }) {
  return <Pressable accessibilityRole="button" accessibilityState={{ disabled: !!disabled }} disabled={disabled} onPress={onPress} style={[s.button, { backgroundColor: secondary ? palette.card : '#005049', borderColor: palette.line, opacity: disabled ? 0.5 : 1 }]}><Text style={{ color: secondary ? palette.text : '#fff', fontWeight: '700', fontSize: 15, textAlign: 'center' }}>{title}</Text></Pressable>;
}
const s = StyleSheet.create({ page: { gap: 12 }, group: { gap: 8 }, card: { padding: 16, borderWidth: 1, borderRadius: 16, gap: 10 }, heading: { fontWeight: '800', marginTop: 12, marginBottom: 6 }, paragraph: { fontSize: 15, lineHeight: 24 }, link: { borderWidth: 1, padding: 14, borderRadius: 12, gap: 4, marginVertical: 3 }, image: { width: '100%', height: 170 }, table: { marginVertical: 8 }, row: { flexDirection: 'row' }, cell: { width: 155, padding: 12, gap: 4 }, form: { gap: 12, paddingVertical: 12, borderBottomWidth: 1 }, label: { fontSize: 13, fontWeight: '600' }, input: { borderWidth: 1, borderRadius: 12, padding: 14, fontSize: 16, minHeight: 50 }, choice: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 8 }, choiceText: { flex: 1, fontSize: 15, lineHeight: 23 }, option: { borderWidth: 1, padding: 12, borderRadius: 10 }, button: { borderWidth: 1, padding: 15, borderRadius: 12, marginVertical: 3 } });
