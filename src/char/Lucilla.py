import time

from src.char.BaseChar import BaseChar, SwitchPriority


class Lucilla(BaseChar):
    """Lucilla 自动战斗: 回路充能型 + 大招变身型角色。

    机制: 长按 E 或蓄力重击各攒 1 格回路能量, 攒满 3 格大招可用; 放大招后变身进入特殊形态
    (技能栏/大招图标消失, 视觉信号全失效), 固定时长输出后变回原建模, 再切人。
    """
    HOLD_TIME: float = 1.4
    LIBERATION_ANIMATION_TIME: float = 3.0
    LIBERATION_HEAVY_TIME: float = 15.0
    HEAVY_PULSE_TIME: float = 0.6
    CHARGE_TIME_OUT: float = 7.2
    LIBERATION_CD_SKIP: float = 1.5
    SWITCH_IN_SETTLE: float = 0.5

    def _has_valid_target(self):
        """检查是否有有效的战斗目标：必须有锁定框且有血量条，或确认为 Boss。"""
        if hasattr(self.task, 'combat_check'):
            combat_check = self.task.combat_check
            if hasattr(combat_check, 'has_target') and hasattr(combat_check, 'has_health_bar'):
                if combat_check.has_target() and combat_check.has_health_bar():
                    return True
                if hasattr(combat_check, 'is_boss') and combat_check.is_boss():
                    return True
                return False
        # 回退到 in_combat()
        return self.task.in_combat()

    def do_perform(self):
        """执行 Lucilla 的站场逻辑：检查有效目标，否则直接切人。"""
        if not self._has_valid_target():
            self.logger.info('Lucilla: No valid target, switch out immediately.')
            self.switch_next_char()
            return

        if not self.perform_combat():
            self.switch_next_char()

    def perform_combat(self):
        """攒能量 -> 大招可用则放大招接输出."""
        start = time.time()
        self.task.wait_until(lambda: self.task.in_team()[0], time_out=0.8)
        self.sleep(self.SWITCH_IN_SETTLE, check_combat=False)
        self.task.next_frame()

        if self.try_liberation():
            return True

        while time.time() - start < self.CHARGE_TIME_OUT:
            if not self._has_valid_target():
                self.logger.info('Lucilla: Target lost during charge loop, stopping.')
                break

            if self.energy_full() and not self.liberation_available():
                self.logger.info('Lucilla: energy full but liberation not castable, switch')
                break

            if not self.liberation_available() and self.task.get_cd('liberation') > self.LIBERATION_CD_SKIP:
                self.logger.info('Lucilla: liberation on long cd, switch to save time')
                break

            if self.try_liberation():
                return True

            self.charge_once()

            if not self._has_valid_target():
                self.logger.info('Lucilla: Target lost after charge, stopping.')
                break

        return False

    def charge_once(self):
        if self.resonance_available():
            self.hold_resonance(self.HOLD_TIME)
        else:
            self.heavy_attack(self.HOLD_TIME)
        self.task.next_frame()

    def try_liberation(self):
        if not self.liberation_available():
            return False
        if not self._has_valid_target():
            return False

        if self.echo_available():
            self.click_echo(time_out=0)

        self.perform_liberation()
        self.switch_next_char()
        return True

    def energy_full(self):
        return self.available('liberation', check_color=True, check_cd=False)

    def perform_liberation(self):
        if not self.task.use_liberation:
            return

        start = time.time()
        while self.liberation_available() and time.time() - start < 1.5:
            self.send_liberation_key()
            self.sleep(0.1, check_combat=False)
        self.record_liberation_use()
        self.logger.info('Lucilla perform lib')

        self.sleep(self.LIBERATION_ANIMATION_TIME, check_combat=False)
        self.pulse_heavy_attack(self.LIBERATION_HEAVY_TIME)
        self.logger.info('Lucilla perform lib end')

    def pulse_heavy_attack(self, total_time):
        end = time.time() + total_time
        seen_active = False
        while time.time() < end:
            if not self._has_valid_target():
                self.logger.info('Lucilla: Target lost during pulse heavy, stopping.')
                break

            self.task.mouse_down()
            try:
                self.sleep(min(self.HEAVY_PULSE_TIME, end - time.time()), check_combat=False)
            finally:
                self.task.mouse_up()

            con = self.task.get_current_con()
            if con > 0.1:
                seen_active = True
            elif seen_active and con < 0.05:
                self.logger.info('Lucilla: transform ended, stop pulse heavy early')
                break

            self.sleep(0.02, check_combat=False)

    def hold_resonance(self, duration):
        self.task.send_key_down(self.get_resonance_key())
        try:
            self.sleep(duration, check_combat=False)
        finally:
            self.task.send_key_up(self.get_resonance_key())
        self.record_resonance_use()

    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        if has_intro and current_char and current_char.char_name in {'char_verina', 'char_shorekeeper'}:
            return SwitchPriority.MUST
        return super().get_switch_priority(current_char, has_intro, target_low_con)
