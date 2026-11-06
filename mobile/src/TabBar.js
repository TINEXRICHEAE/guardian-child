import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';

import { colors } from './theme';

/** Native bottom tabs. Which tabs show depends on who is signed in (see routes.tabsFor). */
export default function TabBar({ tabs, active, dark, onPress }) {
  const insets = useSafeAreaInsets();
  const bar = dark ? colors.darkBar : colors.lightBar;
  const idle = dark ? colors.darkText : colors.lightText;
  const on = dark ? colors.accent : colors.teal;
  return (
    <View style={[styles.bar, { backgroundColor: bar, borderTopColor: dark ? colors.darkLine : colors.lightLine,
                                 paddingBottom: Math.max(insets.bottom, 6) }]}
          accessibilityRole="tablist">
      {tabs.map((t) => {
        const selected = t.key === active;
        return (
          <Pressable key={t.key} onPress={() => onPress(t)} style={styles.tab}
                     accessibilityRole="tab" accessibilityState={{ selected }} accessibilityLabel={t.label}>
            <View style={[styles.mark, { backgroundColor: selected ? on : 'transparent' }]} />
            <Ionicons name={selected ? t.icon.replace('-outline', '') : t.icon} size={22} color={selected ? on : idle} />
            <Text style={[styles.label, { color: selected ? on : idle, fontWeight: selected ? '700' : '600' }]}
                  numberOfLines={1}>{t.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  bar: { flexDirection: 'row', borderTopWidth: 1 },
  tab: { flex: 1, alignItems: 'center', paddingTop: 0, minHeight: 56 },
  mark: { height: 2, alignSelf: 'stretch', marginBottom: 6 },
  label: { fontSize: 11, marginTop: 2 },
});
