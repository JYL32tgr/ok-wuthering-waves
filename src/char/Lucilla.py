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

    def do_perform(self):
        if not self.perform_combat():
            self.switch_next_char()

    def combat_available(self):
        """检查当前是否仍处于真实战斗。

        用于 Lucilla 这种存在长时间固定输出动作的角色。
        避免目标消失后继续执行攻击。
        """
        try:
            return self.in_combat()
        except Exception:
            return False

    def perform_combat(self):
        """攒能量 -> 大招可用则放大招接输出.

        Returns:
            bool: 放出了大招(并已在 try_liberation 内切人)返回 True, 否则 False.
        """

        if not self.combat_available():
            self.logger.info('Lucilla skip: not in combat')
            return False

        start = time.time()

        self.task.wait_until(lambda: self.task.in_team()[0], time_out=0.8)

        if not self.combat_available():
            return False

        self.sleep(self.SWITCH_IN_SETTLE, check_combat=False)
        self.task.next_frame()

        if self.try_liberation():
            return True

        while time.time() - start < self.CHARGE_TIME_OUT:

            if not self.combat_available():
                self.logger.info('Lucilla combat ended during charge')
                break

            if self.energy_full() and not self.liberation_available():
                self.logger.info('Lucilla energy full but liberation not castable, switch')
                break

            if not self.liberation_available() and self.task.get_cd('liberation') > self.LIBERATION_CD_SKIP:
                self.logger.info('Lucilla liberation on long cd, switch to save time')
                break

            if self.try_liberation():
                return True

            self.charge_once()

        return False

    def charge_once(self):
        """攒 1 格回路能量: E 可用优先长按 E、否则蓄力重击。"""

        if not self.combat_available():
            return

        if self.resonance_available():
            self.hold_resonance(self.HOLD_TIME)
        else:
            self.heavy_attack(self.HOLD_TIME)

        self.task.next_frame()

    def try_liberation(self):
        """大招就绪则放招(顺带先放声骸), 返回是否放出。"""

        if not self.combat_available():
            return False

        if not self.liberation_available():
            return False

        if self.echo_available():
            self.click_echo(time_out=0)

        self.perform_liberation()
        self.switch_next_char()
        return True

    def energy_full(self):
        """回路能量是否已满(解放图标高亮, 忽略CD)。"""

        return self.available('liberation', check_color=True, check_cd=False)

    def perform_liberation(self):
        """放大招进入变身形态, 按住左键固定时长输出后切人。"""

        if not self.task.use_liberation:
            return

        start = time.time()

        while self.liberation_available() and time.time() - start < 1.5:
            self.send_liberation_key()
            self.sleep(0.1, check_combat=False)

        self.record_liberation_use()
        self.logger.info('Lucilla perform lib')

        self.sleep(self.LIBERATION_ANIMATION_TIME, check_combat=False)

        if self.combat_available():
            self.pulse_heavy_attack(self.LIBERATION_HEAVY_TIME)

        self.logger.info('Lucilla perform lib end')

    def pulse_heavy_attack(self, total_time):
        """变身后脉冲式重击。

        目标消失或战斗结束时提前停止，避免大世界虚空攻击。
        """

        end = time.time() + total_time
        seen_active = False

        while time.time() < end:

            if not self.combat_available():
                self.logger.info('Lucilla target lost, stop pulse heavy')
                break

            self.task.mouse_down()

            try:
                self.sleep(
                    min(self.HEAVY_PULSE_TIME, end - time.time()),
                    check_combat=False
                )
            finally:
                self.task.mouse_up()

            con = self.task.get_current_con()

            if con > 0.1:
                seen_active = True
            elif seen_active and con < 0.05:
                self.logger.info('Lucilla transform ended, stop pulse heavy early')
                break

            self.sleep(0.02, check_combat=False)

    def hold_resonance(self, duration):
        """长按共鸣技能键一段时间 (攒 1 格回路能量)。"""

        self.task.send_key_down(self.get_resonance_key())

        try:
            self.sleep(duration, check_combat=False)
        finally:
            self.task.send_key_up(self.get_resonance_key())

        self.record_resonance_use()

    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        if has_intro and current_char and current_char.char_name in {'char_verina', 'char_shorekeeper'}:
            return SwitchPriority.MUST

        return super().get_switch_priority(
            current_char,
            has_intro,
            target_low_con
        )
