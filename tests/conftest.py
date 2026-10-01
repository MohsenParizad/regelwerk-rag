"""Shared test fixtures: a tiny law XML in the official gesetze-im-internet format."""
import pytest

from regelrag.ingest import parse_law
from regelrag.retrieve import Retriever

MINI_XML = """<?xml version="1.0" encoding="UTF-8"?>
<dokumente>
  <norm><metadaten><jurabk>SGB 5</jurabk><enbez>§ 275c</enbez>
    <titel format="parat">Durchführung und Umfang von Prüfungen bei Krankenhausbehandlung durch den Medizinischen Dienst</titel></metadaten>
    <textdaten><text format="XML"><Content>
      <P>(1) Bei Krankenhausbehandlung nach § 39 ist eine Prüfung der Rechnung des Krankenhauses spätestens vier Monate nach deren Eingang bei der Krankenkasse einzuleiten. Falls die Prüfung nicht zu einer Minderung des Abrechnungsbetrages führt, hat die Krankenkasse dem Krankenhaus eine Aufwandspauschale in Höhe von 300 Euro zu entrichten.</P>
      <P>(2) Die Prüfquote beträgt<DL Type="arabic"><DT>1.</DT><DD><LA>bis zu 5 Prozent,</LA></DD><DT>2.</DT><DD><LA>bis zu 10 Prozent.</LA></DD></DL></P>
      <P>(3) (weggefallen)</P>
    </Content></text></textdaten></norm>
  <norm><metadaten><jurabk>SGB 5</jurabk><enbez>§ 39</enbez><titel format="parat">Krankenhausbehandlung</titel></metadaten>
    <textdaten><text format="XML"><Content>
      <P>(2) Wählen Versicherte ohne zwingenden Grund ein anderes als ein in der ärztlichen Einweisung genanntes Krankenhaus, können ihnen die Mehrkosten ganz oder teilweise auferlegt werden.</P>
    </Content></text></textdaten></norm>
  <norm><metadaten><jurabk>SGB 5</jurabk><enbez>§ 999</enbez><titel>Nicht ausgewählt</titel></metadaten>
    <textdaten><text format="XML"><Content><P>(1) Irrelevant.</P></Content></text></textdaten></norm>
</dokumente>""".encode()


@pytest.fixture
def passages():
    return parse_law(MINI_XML, "SGB V", ["§ 275c", "§ 39"])


@pytest.fixture
def retriever(passages):
    return Retriever(passages)
