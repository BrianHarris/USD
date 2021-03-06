#!/pxrpythonsubst
#
# Copyright 2018 Pixar
#
# Licensed under the Apache License, Version 2.0 (the "Apache License")
# with the following modification; you may not use this file except in
# compliance with the Apache License and the following modification to it:
# Section 6. Trademarks. is deleted and replaced with:
#
# 6. Trademarks. This License does not grant permission to use the trade
#    names, trademarks, service marks, or product names of the Licensor
#    and its affiliates, except as required to comply with Section 4(c) of
#    the License and to reproduce the content of the NOTICE file.
#
# You may obtain a copy of the Apache License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the Apache License with the above modification is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied. See the Apache License for the specific
# language governing permissions and limitations under the Apache License.

from pxr import Plug
from pxr import Sdf
from pxr import Sdr
from pxr import Tf

import os
import unittest

# The test discovery plugin is installed relative to this script
testRoot = os.path.join(os.path.dirname(__file__), 'SdrPlugins')
testPluginsDsoSearch = testRoot + '/lib/*/Resources/'

class TestShaderNode(unittest.TestCase):
    def test_Registry(self):
        """
        Test basic registry operations. Also ensures that the discovery process
        works correctly.
        """

        # Register test plugins and verify they have been found
        pr = Plug.Registry()
        plugins = pr.RegisterPlugins(testPluginsDsoSearch)

        # Verify the test plugins have been found.  When building monolithic
        # we should find at least these derived types.
        self.assertEqual(len(plugins), 1)
        tdpType  = Tf.Type.FindByName('_NdrTestDiscoveryPlugin')
        tdp2Type = Tf.Type.FindByName('_NdrTestDiscoveryPlugin2')

        tppType = Tf.Type.FindByName('_NdrArgsTestParserPlugin')
        tpp2Type = Tf.Type.FindByName('_NdrOslTestParserPlugin')

        # We don't check for all the derived types of NdrDiscoveryPlugin
        # because this test only uses the discovery and parser plugins 
        # that are defined in this testenv
        assert {tdpType, tdp2Type}.issubset(
            set(pr.GetAllDerivedTypes('NdrDiscoveryPlugin')))
        assert {tppType, tpp2Type}.issubset(
            set(pr.GetAllDerivedTypes('NdrParserPlugin')))

        # The following source types are what we expect to discover from
        # _NdrTestDiscoveryPlugin and _NdrTestDiscoveryPlugin2.  Note that there
        # is no glslfx parser plugin provided in this test.
        argsType = "RmanCpp"
        oslType = "OSL"
        glslfxType = "glslfx"

        # Instantiating the registry will kick off the discovery process.
        # This test assumes the PXR_NDR_SKIP_DISCOVERY_PLUGIN_DISCOVERY 
        # and PXR_NDR_SKIP_PARSER_PLUGIN_DISCOVERY has been set prior to 
        # being run to ensure built-in plugins are not found. Instead 
        # we'll list the plugins we want explicitly.

        # Setting this from within the script does not work on Windows.
        # os.environ["PXR_NDR_SKIP_DISCOVERY_PLUGIN_DISCOVERY"] = ""
        # os.environ["PXR_NDR_SKIP_PARSER_PLUGIN_DISCOVERY"] = ""
        reg = Sdr.Registry()

        # Set up the test parser plugins.
        reg.SetExtraParserPlugins([tppType, tpp2Type])

        # We will register the discovery plugins one by one so that we can check
        # source types are not duplicated in the registry if we have plugins
        # that discover nodes of the same source type

        # The _NdrTestDiscoveryPlugin should find discovery results that have
        # source types of RmanCpp and OSL
        reg.SetExtraDiscoveryPlugins([tdpType])
        assert reg.GetAllNodeSourceTypes() == [oslType, argsType]

        # The _NdrTestDiscoveryPlugin2 should find discovery results that have
        # source types of RmanCpp and glslfx
        reg.SetExtraDiscoveryPlugins([tdp2Type])

        # Test that the registry does not see 'RmanCpp' twice as a source type,
        # and that it finds 'glslfx' as a source type
        assert reg.GetAllNodeSourceTypes() == [oslType, argsType, glslfxType]

        # Calling SdrRegistry::GetShaderNodesByFamily() will actually parse the
        # discovery results.
        # Notice that in the five node names we find, we get 'TestNodeSameName'
        # twice because there are two nodes with different source types that
        # have the same name.
        # Notice that we do not see 'TestNodeGLSLFX' because we don't have a
        # parser plugin to support it
        nodes = reg.GetShaderNodesByFamily()
        shaderNodeNames = [node.GetName() for node in nodes]
        assert set(shaderNodeNames) == {
            "TestNodeARGS",
            "TestNodeARGS2",
            "TestNodeOSL",
            "TestNodeSameName",
            "TestNodeSameName"
        }

        assert reg.GetSearchURIs() == ["/TestSearchPath", "/TestSearchPath2"]

        # Calling SdrRegistry::GetNodeNames only looks at discovery results
        # without parsing them.
        # Notice that we get 'TestNodeSameName' only once because we only show
        # unique names.
        # Notice that we see 'TestNodeGLSLFX' because it is in our discovery
        # results even though we do not have a parser plugin that supports its
        # source type.
        assert set(reg.GetNodeNames()) == {
            "TestNodeARGS",
            "TestNodeARGS2",
            "TestNodeOSL",
            "TestNodeSameName",
            "TestNodeGLSLFX"
        }
        # Verify that GetNodeIdentifiers follows the same rules as GetNodeNames.
        # Note that the names and identifiers do happen to be the same in this
        # test case which is common.
        assert set(reg.GetNodeIdentifiers()) == {
            "TestNodeARGS",
            "TestNodeARGS2",
            "TestNodeOSL",
            "TestNodeSameName",
            "TestNodeGLSLFX"
        }

        assert id(reg.GetShaderNodeByName(nodes[0].GetName())) == id(nodes[0])

        nodeName = "TestNodeSameName"
        nodeIdentifier = "TestNodeSameName"
        nodeAlias = "Alias_TestNodeSameName"

        # Ensure that the registry can retrieve two nodes of the same name but
        # different source types
        assert len(reg.GetShaderNodesByName(nodeName)) == 2
        node = reg.GetShaderNodeByNameAndType(nodeName, oslType)
        assert node is not None
        node = reg.GetShaderNodeByNameAndType(nodeName, argsType) 
        assert node is not None
        node = reg.GetShaderNodeByName(nodeName, [oslType, argsType])
        assert node.GetSourceType() == oslType
        node = reg.GetShaderNodeByName(nodeName, [argsType, oslType])
        assert node.GetSourceType() == argsType

        # Ensure that the registry can retrieve these same nodes via identifier,
        # which, in these cases, are the same as the node names.
        assert len(reg.GetShaderNodesByIdentifier(nodeIdentifier)) == 2
        node = reg.GetShaderNodeByIdentifierAndType(nodeIdentifier, oslType) 
        assert node is not None
        node = reg.GetShaderNodeByIdentifierAndType(nodeIdentifier, argsType) 
        assert node is not None
        node = reg.GetShaderNodeByIdentifier(nodeIdentifier, [oslType, argsType])
        assert node.GetSourceType() == oslType
        node = reg.GetShaderNodeByIdentifier(nodeIdentifier, [argsType, oslType])
        assert node.GetSourceType() == argsType

        # Test aliases. The discovery result for the args type 
        # "TestNodeSameName" has been given an alias by its discovery plugin
        # (see TestSdrPlugin_discoveryPlugin.cpp).
        # The args type node can be found by its alias through the 
        # GetShaderNodeByIdentifier APIs. The osl type node is not found 
        # by this alias
        assert len(reg.GetShaderNodesByIdentifier(nodeAlias)) == 1
        node = reg.GetShaderNodeByIdentifierAndType(nodeAlias, oslType)
        assert node is None
        node = reg.GetShaderNodeByIdentifierAndType(nodeAlias, argsType)
        assert node is not None
        assert node.GetIdentifier() == nodeIdentifier 
        assert node.GetSourceType() == argsType
        node = reg.GetShaderNodeByIdentifier(nodeAlias, [oslType, argsType])
        assert node.GetIdentifier() == nodeIdentifier 
        assert node.GetSourceType() == argsType
        node = reg.GetShaderNodeByIdentifier(nodeAlias, [argsType, oslType])
        assert node.GetIdentifier() == nodeIdentifier 
        assert node.GetSourceType() == argsType

        # Ensure that GetShaderNodeByName APIs are NOT able to find nodes using 
        # aliases.
        assert len(reg.GetShaderNodesByName(nodeAlias)) == 0
        node = reg.GetShaderNodeByNameAndType(nodeAlias, oslType)
        assert node is None
        node = reg.GetShaderNodeByNameAndType(nodeAlias, argsType) 
        assert node is None
        node = reg.GetShaderNodeByName(nodeAlias, [oslType, argsType])
        assert node is None
        node = reg.GetShaderNodeByName(nodeAlias, [argsType, oslType])
        assert node is None

        # Test GetShaderNodeFromAsset to check that a subidentifier is part of
        # the node's identifier if one is specified
        node = reg.GetShaderNodeFromAsset(
            Sdf.AssetPath('TestNodeSourceAsset.oso'),   # shaderAsset
            {},                                         # metadata
            "mySubIdentifier")                          # subIdentifier
        assert node.GetIdentifier().endswith("<mySubIdentifier><>")
        assert node.GetName() == "TestNodeSourceAsset.oso"

        # Test GetShaderNodeFromAsset to check that a sourceType is part of
        # the node's identifier if one is specified
        node = reg.GetShaderNodeFromAsset(
            Sdf.AssetPath('TestNodeSourceAsset.oso'),   # shaderAsset
            {},                                         # metadata
            "mySubIdentifier",                          # subIdentifier
            "OSL")                                      # sourceType
        assert node.GetIdentifier().endswith("<mySubIdentifier><OSL>")


if __name__ == '__main__':
    unittest.main()
