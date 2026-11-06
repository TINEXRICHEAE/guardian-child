import { Linking, Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { colors } from './theme';

/** Shown when Guardian cannot be reached. Help (116) never depends on the network being up. */
export default function OfflineScreen({ siteUrl, detail, onRetry }) {
  return (
    <View style={styles.wrap}>
      <Ionicons name="cloud-offline-outline" size={48} color={colors.teal} />
      <Text style={styles.title}>Guardian can't be reached</Text>
      <Text style={styles.body}>Check your internet connection and try again. Until then, don't reply to, pay or click anything you're unsure about.</Text>
      <Pressable style={styles.primary} onPress={onRetry} accessibilityRole="button">
        <Text style={styles.primaryText}>Try again</Text>
      </Pressable>
      <Pressable style={styles.secondary} onPress={() => Linking.openURL('tel:116')} accessibilityRole="button">
        <Text style={styles.secondaryText}>Need help now? Call 116 (free)</Text>
      </Pressable>
      <Text style={styles.detail}>{siteUrl}{detail ? `\n${detail}` : ''}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 28, backgroundColor: colors.lightBg },
  title: { fontSize: 20, fontWeight: '700', color: '#1a1c1c', marginTop: 12, marginBottom: 8, textAlign: 'center' },
  body: { fontSize: 15, color: colors.lightText, textAlign: 'center', marginBottom: 22, lineHeight: 21 },
  primary: { backgroundColor: colors.primary, paddingVertical: 12, paddingHorizontal: 28, marginBottom: 12 },
  primaryText: { color: '#fff', fontWeight: '700', fontSize: 15 },
  secondary: { borderWidth: 2, borderColor: colors.primary, paddingVertical: 10, paddingHorizontal: 20 },
  secondaryText: { color: colors.primary, fontWeight: '700', fontSize: 14 },
  detail: { fontSize: 11, color: '#6f7977', marginTop: 24, textAlign: 'center' },
});
